#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is free software. It is made
 * available to you under the terms of the GNU General Public License
 * as published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version. For more
 * information, see COPYING.
 */
#endregion

using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using OpenRA.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.Common.Traits
{
	[TraitLocation(SystemActors.World)]
	[Desc("A city of 3D building meshes standing on a ground image, both read from the map package",
		"(written by tools/warsaw/build_city.py). Drawn only by the perspective camera (PerspectiveCamera in mod.yaml).",
		"Each mesh belongs to a CityBuilding actor, which blocks its cells and hides the mesh when it is removed.")]
	public class CityMapInfo : TraitInfo
	{
		[Desc("Building meshes and footprints (format in build_city.py). Empty or missing = none.")]
		public readonly string Meshes = "buildings.mesh";

		[Desc("Placed textured city models and their atlas (tools/city/build_city_map.py). Missing = none.")]
		public readonly string Scene = "scene.mesh";
		public readonly string SceneAtlas = "scene_atlas.png";

		[Desc("Light on the scene models, whose textures carry no baked shading.")]
		public readonly float[] SceneAmbientLight = { 0.58f, 0.58f, 0.62f };
		public readonly float[] SceneDiffuseLight = { 0.62f, 0.58f, 0.50f };

		[Desc("Ground image stretched over the map's playable bounds. Empty = draw the terrain tiles instead.")]
		public readonly string Ground = "ground.png";

		[Desc("Facade atlas: FacadeAtlasGrid x FacadeAtlasGrid tiles, two per style (upper floors, ground floor).")]
		public readonly string Facades = "facades.png";
		public readonly int FacadeAtlasGrid = 4;

		[Desc("Image draped over the roofs, covering the map's playable bounds (the orthophoto).")]
		public readonly string Roofs = "roofs.png";

		[Desc("Streets: ground layers, kerbs and markings, plus instanced props (format in build_streets.py).",
			"Empty or missing = none.")]
		public readonly string Streets = "streets.mesh";

		[Desc("Seamless ground surface atlas for the streets, FacadeAtlasGrid x FacadeAtlasGrid tiles.")]
		public readonly string Surfaces = "surfaces.png";

		[Desc("Compass bearing (0 = north, clockwise) and elevation of the sun.")]
		public readonly WAngle SunYaw = WAngle.FromDegrees(225);
		public readonly WAngle SunPitch = WAngle.FromDegrees(45);

		[Desc("The facade renders already carry their own shading, so the sun only adds a modest directional term.")]
		public readonly float[] AmbientLight = { 0.78f, 0.78f, 0.80f };
		public readonly float[] DiffuseLight = { 0.34f, 0.32f, 0.28f };

		public override object Create(ActorInitializer init) { return new CityMap(init.World, this); }
	}

	public sealed class CityMap : IRenderWorld3D, IWorldLoaded, INotifyActorDisposing
	{
		const uint Version = 2;

		readonly CityMapInfo info;
		readonly CPos[][] footprints;
		readonly (int Start, int Count)[] ranges;
		readonly bool[] visible;
		readonly IVertexBuffer<MeshVertex> vertexBuffer;
		readonly IShader shader;
		readonly float[] light;
		readonly Sprite ground;
		readonly Sheet facades;
		readonly Sheet roofs;
		readonly ITexture styleTable;
		readonly CellLayer<float> roofs3D;
		readonly CityScene scene;

		// Streets (all null when the map has none).
		readonly IVertexBuffer<MeshVertex> streetGround;
		readonly int streetGroundCount;
		readonly IVertexBuffer<MeshVertex> propVertices;
		readonly (int Start, int Count)[] propModels;
		readonly (int Model, int First, int Count)[] propGroups;
		readonly ITexture propInstances;
		readonly ITexture surfaceTable;
		readonly Sheet surfaces;
		readonly IShader propShader;
		bool disposed;

		public CityMap(World world, CityMapInfo info)
		{
			this.info = info;

			var vertices = Array.Empty<MeshVertex>();
			var styles = Array.Empty<float>();
			footprints = Array.Empty<CPos[]>();
			ranges = Array.Empty<(int, int)>();
			if (!string.IsNullOrEmpty(info.Meshes) && world.Map.Exists(info.Meshes))
				using (var s = world.Map.Open(info.Meshes))
					(styles, footprints, ranges, vertices) = Read(s);

			// (width, upper, ground) per style as one RGBA16F texel each, read with texelFetch.
			var width = Exts.NextPowerOf2(Math.Max(styles.Length / 3, 1));
			var table = new float[4 * width];
			for (var i = 0; i < styles.Length / 3; i++)
				Array.Copy(styles, 3 * i, table, 4 * i, 3);

			styleTable = Game.Renderer.CreateTexture();
			styleTable.ScaleFilter = TextureScaleFilter.Nearest;
			styleTable.SetFloatData(table, width, 1);

			facades = Exists(world, info.Facades) ? LoadMipmapped(world, info.Facades) : null;
			roofs = Exists(world, info.Roofs) ? LoadMipmapped(world, info.Roofs) : null;

			visible = new bool[ranges.Length];
			Array.Fill(visible, true);

			// Tallest roof (world px) standing on each cell, for the camera's roof collision.
			roofs3D = new CellLayer<float>(world.Map);
			roofs3D.Clear(float.NegativeInfinity);
			for (var i = 0; i < ranges.Length; i++)
			{
				var top = float.NegativeInfinity;
				for (var v = ranges[i].Start; v < ranges[i].Start + ranges[i].Count; v++)
					top = Math.Max(top, vertices[v].Y);

				foreach (var c in footprints[i])
					if (roofs3D.Contains(c))
						roofs3D[c] = Math.Max(roofs3D[c], top);
			}

			vertexBuffer = Game.Renderer.CreateVertexBuffer<MeshVertex>(Math.Max(vertices.Length, 1));
			if (vertices.Length > 0)
				vertexBuffer.SetData(vertices, vertices.Length);

			if (Exists(world, info.Scene))
			{
				scene = new CityScene(world, info.Scene, info.SceneAtlas);
				for (var y = 0; y < scene.CellsHigh; y++)
					for (var x = 0; x < scene.CellsWide; x++)
						if (roofs3D.Contains(new CPos(x, y)))
							roofs3D[new CPos(x, y)] = Math.Max(roofs3D[new CPos(x, y)], scene.CellHeights[y * scene.CellsWide + x]);
			}
			shader = Game.Renderer.CreateShader(new MeshShaderBindings());

			// Direction towards the sun in the camera frame (x east, y up, z south).
			var yaw = info.SunYaw.Angle * Math.PI / 512;
			var pitch = info.SunPitch.Angle * Math.PI / 512;
			light = new[] { (float)(Math.Sin(yaw) * Math.Cos(pitch)), (float)Math.Sin(pitch), (float)(-Math.Cos(yaw) * Math.Cos(pitch)) };

			if (!string.IsNullOrEmpty(info.Ground))
			{
				var sheet = LoadMipmapped(world, info.Ground);
				ground = new Sprite(sheet, new Rectangle(0, 0, sheet.Size.Width, sheet.Size.Height), TextureChannel.RGBA);
			}

			if (!string.IsNullOrEmpty(info.Streets) && world.Map.Exists(info.Streets))
			{
				float[] surfaceSizes, instances;
				MeshVertex[] groundVertices, modelVertices;
				using (var st = world.Map.Open(info.Streets))
					(surfaceSizes, groundVertices, modelVertices, propModels, instances, propGroups) = ReadStreets(st);

				surfaceTable = Game.Renderer.CreateTexture();
				surfaceTable.SetFloatData(Table(surfaceSizes, 1), Exts.NextPowerOf2(Math.Max(surfaceSizes.Length, 1)), 1);
				surfaces = LoadMipmapped(world, info.Surfaces);

				streetGroundCount = groundVertices.Length;
				streetGround = Game.Renderer.CreateVertexBuffer<MeshVertex>(Math.Max(streetGroundCount, 1));
				if (streetGroundCount > 0)
					streetGround.SetData(groundVertices, streetGroundCount);

				propVertices = Game.Renderer.CreateVertexBuffer<MeshVertex>(Math.Max(modelVertices.Length, 1));
				if (modelVertices.Length > 0)
					propVertices.SetData(modelVertices, modelVertices.Length);

				// Two RGBA32F texels per instance, 512 instances per row (see prop.vert).
				const int Row = 512;
				var rows = Exts.NextPowerOf2(Math.Max((instances.Length / 8 + Row - 1) / Row, 1));
				var data = new float[2 * Row * rows * 4];
				Array.Copy(instances, data, instances.Length);
				propInstances = Game.Renderer.CreateTexture();
				propInstances.SetFloatData(data, 2 * Row, rows);
				propShader = Game.Renderer.CreateShader(new PropShaderBindings());
			}
		}

		/// <summary>Packs groups of <paramref name="stride"/> floats into RGBA texels, one per group.</summary>
		static float[] Table(float[] values, int stride)
		{
			var count = values.Length / stride;
			var table = new float[4 * Exts.NextPowerOf2(Math.Max(count, 1))];
			for (var i = 0; i < count; i++)
				Array.Copy(values, stride * i, table, 4 * i, stride);

			return table;
		}

		static MeshVertex[] ReadVertices(BinaryReader reader, int count)
		{
			var vertices = new MeshVertex[count];
			reader.ReadBytes(count * Marshal.SizeOf<MeshVertex>()).AsSpan().CopyTo(MemoryMarshal.AsBytes(vertices.AsSpan()));
			return vertices;
		}

		static (float[], MeshVertex[], MeshVertex[], (int, int)[], float[], (int, int, int)[]) ReadStreets(Stream s)
		{
			using var reader = new BinaryReader(s);
			if (new string(reader.ReadChars(4)) != "WSTR" || reader.ReadUInt32() != 1)
				throw new InvalidDataException("Not a version 1 WSTR streets file (rebuild it with tools/warsaw/build_city.py).");

			var sizes = new float[reader.ReadUInt32()];
			for (var i = 0; i < sizes.Length; i++)
				sizes[i] = reader.ReadSingle();

			var ground = ReadVertices(reader, (int)reader.ReadUInt32());

			var modelCount = (int)reader.ReadUInt32();
			var models = new List<MeshVertex>();
			var ranges = new (int, int)[modelCount];
			for (var m = 0; m < modelCount; m++)
			{
				var count = (int)reader.ReadUInt32();
				ranges[m] = (models.Count, count);
				models.AddRange(ReadVertices(reader, count));
			}

			// Instances arrive sorted by model: x, z, yaw, scale, r, g, b plus one pad, per instance.
			var instanceCount = (int)reader.ReadUInt32();
			var instances = new float[8 * instanceCount];
			var groups = new List<(int, int, int)>();
			for (var i = 0; i < instanceCount; i++)
			{
				var model = (int)reader.ReadUInt32();
				for (var k = 0; k < 7; k++)
					instances[8 * i + k] = reader.ReadSingle();

				if (groups.Count == 0 || groups[^1].Item1 != model)
					groups.Add((model, i, 0));

				var g = groups[^1];
				groups[^1] = (g.Item1, g.Item2, g.Item3 + 1);
			}

			return (sizes, ground, models.ToArray(), ranges, instances, groups.ToArray());
		}

		static bool Exists(World world, string filename)
		{
			return !string.IsNullOrEmpty(filename) && world.Map.Exists(filename);
		}

		static Sheet LoadMipmapped(World world, string filename)
		{
			using var s = world.Map.Open(filename);
			var sheet = new Sheet(SheetType.BGRA, s);
			sheet.GetTexture().ScaleFilter = TextureScaleFilter.Mipmapped;
			return sheet;
		}

		static (float[] Styles, CPos[][] Footprints, (int, int)[] Ranges, MeshVertex[] Vertices) Read(Stream s)
		{
			using var reader = new BinaryReader(s);
			if (new string(reader.ReadChars(4)) != "WMSH" || reader.ReadUInt32() != Version)
				throw new InvalidDataException($"Not a version {Version} WMSH city mesh file (rebuild it with tools/warsaw/build_city.py).");

			var styles = new float[3 * reader.ReadUInt32()];
			for (var i = 0; i < styles.Length; i++)
				styles[i] = reader.ReadSingle();

			var count = (int)reader.ReadUInt32();
			var footprints = new CPos[count][];
			var ranges = new (int, int)[count];
			var chunks = new List<byte[]>(count);
			var total = 0;
			var stride = Marshal.SizeOf<MeshVertex>();
			for (var i = 0; i < count; i++)
			{
				var vertexCount = (int)reader.ReadUInt32();
				var cellCount = (int)reader.ReadUInt32();
				var cells = new CPos[cellCount];
				for (var c = 0; c < cellCount; c++)
					cells[c] = new CPos(reader.ReadUInt16(), reader.ReadUInt16());

				footprints[i] = cells;
				ranges[i] = (total, vertexCount);
				chunks.Add(reader.ReadBytes(vertexCount * stride));
				total += vertexCount;
			}

			var vertices = new MeshVertex[total];
			var bytes = MemoryMarshal.AsBytes(vertices.AsSpan());
			var offset = 0;
			foreach (var chunk in chunks)
			{
				chunk.AsSpan().CopyTo(bytes[offset..]);
				offset += chunk.Length;
			}

			return (styles, footprints, ranges, vertices);
		}

		void IWorldLoaded.WorldLoaded(World w, WorldRenderer wr)
		{
			var camera = wr.Viewport.Camera;
			if (camera == null)
				return;

			var cellPx = wr.TileSize.Height;
			camera.RoofHeight = (ground, radius) =>
			{
				var r = (int)Math.Ceiling(radius / cellPx);
				var cx = (int)Math.Floor(ground.X / cellPx);
				var cy = (int)Math.Floor(ground.Y / cellPx);
				var top = float.NegativeInfinity;
				for (var y = cy - r; y <= cy + r; y++)
				{
					for (var x = cx - r; x <= cx + r; x++)
					{
						var c = new CPos(x, y);
						if (roofs3D.Contains(c))
							top = Math.Max(top, roofs3D[c]);
					}
				}

				return top;
			};
		}

		/// <summary>Map cells building <paramref name="index"/> stands on (may be empty for a tiny one).</summary>
		public IReadOnlyList<CPos> Footprint(int index) { return footprints[index]; }

		public void SetVisible(int index, bool value) { visible[index] = value; }

		void SetCommonUniforms(IShader s, Camera3D camera)
		{
			// Copied: the threaded context posts the array to the render thread, and the camera rewrites it next frame.
			s.SetMatrix("ViewProjection", (float[])camera.RenderViewProjection.Clone());
			s.SetVec("LightDirection", light, 3);
			s.SetVec("AmbientLight", info.AmbientLight, 3);
			s.SetVec("DiffuseLight", info.DiffuseLight, 3);
			s.SetVec("Eye", camera.Eye.X, camera.Eye.Y, camera.Eye.Z);
			s.SetVec("HazeRange", camera.HazeRange.X, camera.HazeRange.Y);
			s.SetVec("SkyColour", camera.SkyColour, 3);
		}

		void SetMeshTextures()
		{
			if (facades != null)
				shader.SetTexture("Facades", facades.GetTexture());

			if (roofs != null)
				shader.SetTexture("Roofs", roofs.GetTexture());

			shader.SetTexture("StyleTable", styleTable);
			shader.SetVec("AtlasGrid", info.FacadeAtlasGrid);
			if (surfaces != null)
			{
				shader.SetTexture("Surfaces", surfaces.GetTexture());
				shader.SetTexture("SurfaceTable", surfaceTable);
			}
		}

		void IRenderWorld3D.RenderGround(WorldRenderer wr)
		{
			var camera = wr.Viewport.Camera;
			if (streetGround != null && streetGroundCount > 0 && camera != null)
			{
				// Painter's order, no depth: the layers lie centimetres apart, which a depth buffer cannot
				// separate at city distances. The file lists them bottom-up (build_streets.py).
				Game.Renderer.Flush();
				SetCommonUniforms(shader, camera);
				SetMeshTextures();
				shader.PrepareRender();
				Game.Renderer.DrawBatch(streetGround, shader, 0, streetGroundCount, PrimitiveType.TriangleList);
			}

			if (ground == null)
				return;

			var map = wr.World.Map;
			var tl = wr.ScreenPxPosition(map.ProjectedTopLeft);
			var br = wr.ScreenPxPosition(map.ProjectedBottomRight);
			var scale = new float3((float)(br.X - tl.X) / ground.Size.X, (float)(br.Y - tl.Y) / ground.Size.Y, 1f);

			// A photograph, not pixel art: draw it with plain (mipmapped) filtering, then restore the world default.
			Game.Renderer.Flush();
			Game.Renderer.WorldSpriteRenderer.EnablePixelArtScaling(false);
			Game.Renderer.WorldRgbaSpriteRenderer.DrawSprite(ground, new float3(tl.X, tl.Y, 0), scale);
			Game.Renderer.Flush();
			Game.Renderer.WorldSpriteRenderer.EnablePixelArtScaling(true);
		}

		void IRenderWorld3D.RenderMeshes(WorldRenderer wr)
		{
			var camera = wr.Viewport.Camera;
			if (camera == null)
				return;

			SetCommonUniforms(shader, camera);
			SetMeshTextures();
			shader.PrepareRender();

			// One draw per run of consecutive standing buildings: a single call until something is destroyed.
			var start = -1;
			var end = 0;
			for (var i = 0; i <= ranges.Length; i++)
			{
				if (i < ranges.Length && visible[i])
				{
					if (start < 0)
						start = ranges[i].Start;

					end = ranges[i].Start + ranges[i].Count;
					continue;
				}

				if (start >= 0 && end > start)
					Game.Renderer.DrawBatch(vertexBuffer, shader, start, end - start, PrimitiveType.TriangleList);

				start = -1;
			}

			scene?.Render(camera, light, info.SceneAmbientLight, info.SceneDiffuseLight);

			if (propShader == null)
				return;

			SetCommonUniforms(propShader, camera);
			propShader.SetTexture("Instances", propInstances);
			foreach (var (model, first, count) in propGroups)
			{
				propShader.SetVec("InstanceBase", first);
				propShader.PrepareRender();
				Game.Renderer.DrawBatchInstanced(propVertices, propShader, propModels[model].Start, propModels[model].Count, count, PrimitiveType.TriangleList);
			}
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			if (disposed)
				return;

			vertexBuffer.Dispose();
			ground?.Sheet.Dispose();
			facades?.Dispose();
			roofs?.Dispose();
			scene?.Dispose();
			styleTable.Dispose();
			streetGround?.Dispose();
			propVertices?.Dispose();
			propInstances?.Dispose();
			surfaceTable?.Dispose();
			surfaces?.Dispose();
			disposed = true;
		}
	}
}
