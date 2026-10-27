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
		[Desc("Building meshes and footprints (format in build_city.py).")]
		public readonly string Meshes = "buildings.mesh";

		[Desc("Ground image stretched over the map's playable bounds. Empty = draw the terrain tiles instead.")]
		public readonly string Ground = "ground.png";

		[Desc("Compass bearing (0 = north, clockwise) and elevation of the sun.")]
		public readonly WAngle SunYaw = WAngle.FromDegrees(225);
		public readonly WAngle SunPitch = WAngle.FromDegrees(45);

		public readonly float[] AmbientLight = { 0.55f, 0.55f, 0.58f };
		public readonly float[] DiffuseLight = { 0.62f, 0.58f, 0.51f };

		public override object Create(ActorInitializer init) { return new CityMap(init.World, this); }
	}

	public sealed class CityMap : IRenderWorld3D, INotifyActorDisposing
	{
		const uint Version = 1;

		readonly CityMapInfo info;
		readonly CPos[][] footprints;
		readonly (int Start, int Count)[] ranges;
		readonly bool[] visible;
		readonly IVertexBuffer<MeshVertex> vertexBuffer;
		readonly IShader shader;
		readonly float[] light;
		readonly Sprite ground;
		bool disposed;

		public CityMap(World world, CityMapInfo info)
		{
			this.info = info;

			MeshVertex[] vertices;
			using (var s = world.Map.Open(info.Meshes))
				(footprints, ranges, vertices) = Read(s);

			visible = new bool[ranges.Length];
			Array.Fill(visible, true);

			vertexBuffer = Game.Renderer.CreateVertexBuffer<MeshVertex>(vertices.Length);
			vertexBuffer.SetData(vertices, vertices.Length);
			shader = Game.Renderer.CreateShader(new MeshShaderBindings());

			// Direction towards the sun in the camera frame (x east, y up, z south).
			var yaw = info.SunYaw.Angle * Math.PI / 512;
			var pitch = info.SunPitch.Angle * Math.PI / 512;
			light = new[] { (float)(Math.Sin(yaw) * Math.Cos(pitch)), (float)Math.Sin(pitch), (float)(-Math.Cos(yaw) * Math.Cos(pitch)) };

			if (!string.IsNullOrEmpty(info.Ground))
			{
				using (var s = world.Map.Open(info.Ground))
				{
					var sheet = new Sheet(SheetType.BGRA, s);
					ground = new Sprite(sheet, new Rectangle(0, 0, sheet.Size.Width, sheet.Size.Height), TextureChannel.RGBA);
				}
			}
		}

		static (CPos[][] Footprints, (int, int)[] Ranges, MeshVertex[] Vertices) Read(Stream s)
		{
			using var reader = new BinaryReader(s);
			if (new string(reader.ReadChars(4)) != "WMSH" || reader.ReadUInt32() != Version)
				throw new InvalidDataException("Not a version 1 WMSH city mesh file.");

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

			return (footprints, ranges, vertices);
		}

		/// <summary>Map cells building <paramref name="index"/> stands on (may be empty for a tiny one).</summary>
		public IReadOnlyList<CPos> Footprint(int index) { return footprints[index]; }

		public void SetVisible(int index, bool value) { visible[index] = value; }

		void IRenderWorld3D.RenderGround(WorldRenderer wr)
		{
			if (ground == null)
				return;

			var map = wr.World.Map;
			var tl = wr.ScreenPxPosition(map.ProjectedTopLeft);
			var br = wr.ScreenPxPosition(map.ProjectedBottomRight);
			var scale = new float3((float)(br.X - tl.X) / ground.Size.X, (float)(br.Y - tl.Y) / ground.Size.Y, 1f);
			Game.Renderer.WorldRgbaSpriteRenderer.DrawSprite(ground, new float3(tl.X, tl.Y, 0), scale);
		}

		void IRenderWorld3D.RenderMeshes(WorldRenderer wr)
		{
			var camera = wr.Viewport.Camera;
			if (camera == null)
				return;

			// Copied: the threaded context posts the array to the render thread, and the camera rewrites it next frame.
			shader.SetMatrix("ViewProjection", (float[])camera.ViewProjection.Clone());
			shader.SetVec("LightDirection", light, 3);
			shader.SetVec("AmbientLight", info.AmbientLight, 3);
			shader.SetVec("DiffuseLight", info.DiffuseLight, 3);
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
		}

		void INotifyActorDisposing.Disposing(Actor self)
		{
			if (disposed)
				return;

			vertexBuffer.Dispose();
			ground?.Sheet.Dispose();
			disposed = true;
		}
	}
}
