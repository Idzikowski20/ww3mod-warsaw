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
using System.IO;
using System.Runtime.InteropServices;
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA.Mods.Common.Traits
{
	/// <summary>
	/// Textured city models placed several times over the map (tools/city/build_city_map.py). A model is a set
	/// of meshes drawn with instancing (the generator's wall modules, props and trees); each placement is a
	/// model at a ground point with a yaw and an optional mirror, skipped when its bounds are outside the
	/// camera's view or past the haze.
	/// </summary>
	sealed class CityScene : IDisposable
	{
		const uint Version = 2;

		// Four RGBA32F texels (a 3x4 matrix and padding) per instance, this many instances per texture row (see scene.vert).
		const int Row = 1024;

		readonly IVertexBuffer<SceneVertex> vertices;
		readonly (int First, int Count)[] meshes;
		readonly (float3 Min, float3 Max, (int Mesh, int First, int Count)[] Batches)[] models;
		readonly (int Model, float X, float Z, float Yaw, float Mirror)[] placements;
		readonly ITexture instances;
		readonly Sheet atlas;
		readonly IShader shader;

		/// <summary>Tallest scene geometry over each cell, world px, NegativeInfinity where open (for roof collision).</summary>
		public readonly float[] CellHeights;
		public readonly int CellsWide, CellsHigh;

		public CityScene(World world, string file, string atlasFile)
		{
			using (var s = world.Map.Open(file))
			using (var reader = new BinaryReader(s))
			{
				if (new string(reader.ReadChars(4)) != "WSCN" || reader.ReadUInt32() != Version)
					throw new InvalidDataException($"{file} is not a version {Version} WSCN scene (rebuild it with tools/city/build_city_map.py).");

				meshes = new (int, int)[reader.ReadUInt32()];
				var vertexTotal = (int)reader.ReadUInt32();
				for (var m = 0; m < meshes.Length; m++)
					meshes[m] = ((int)reader.ReadUInt32(), (int)reader.ReadUInt32());

				var v = new SceneVertex[vertexTotal];
				reader.ReadBytes(vertexTotal * Marshal.SizeOf<SceneVertex>()).AsSpan().CopyTo(MemoryMarshal.AsBytes(v.AsSpan()));
				vertices = Game.Renderer.CreateVertexBuffer<SceneVertex>(Math.Max(vertexTotal, 1));
				vertices.SetData(v, vertexTotal);

				models = new (float3, float3, (int, int, int)[])[reader.ReadUInt32()];
				for (var m = 0; m < models.Length; m++)
				{
					var min = new float3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
					var max = new float3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
					var batches = new (int, int, int)[reader.ReadUInt32()];
					for (var b = 0; b < batches.Length; b++)
						batches[b] = ((int)reader.ReadUInt32(), (int)reader.ReadUInt32(), (int)reader.ReadUInt32());

					models[m] = (min, max, batches);
				}

				var instanceTotal = (int)reader.ReadUInt32();
				var rows = Exts.NextPowerOf2(Math.Max((instanceTotal + Row - 1) / Row, 1));
				var data = new float[4 * Row * rows * 4];
				for (var i = 0; i < instanceTotal; i++)
					for (var k = 0; k < 12; k++)
						data[16 * i + k] = reader.ReadSingle();

				instances = Game.Renderer.CreateTexture();
				instances.SetFloatData(data, 4 * Row, rows);

				placements = new (int, float, float, float, float)[reader.ReadUInt32()];
				for (var i = 0; i < placements.Length; i++)
					placements[i] = ((int)reader.ReadUInt32(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());

				CellsWide = (int)reader.ReadUInt32();
				CellsHigh = (int)reader.ReadUInt32();
				CellHeights = new float[CellsWide * CellsHigh];
				for (var i = 0; i < CellHeights.Length; i++)
					CellHeights[i] = reader.ReadSingle();
			}

			using (var s = world.Map.Open(atlasFile))
				atlas = new Sheet(SheetType.BGRA, s);

			atlas.GetTexture().ScaleFilter = TextureScaleFilter.Mipmapped;
			shader = Game.Renderer.CreateShader(new SceneShaderBindings());
		}

		public void Render(Camera3D camera, float[] light, float[] ambient, float[] diffuse)
		{
			shader.SetMatrix("ViewProjection", (float[])camera.RenderViewProjection.Clone());
			shader.SetVec("LightDirection", light, 3);
			shader.SetVec("AmbientLight", ambient, 3);
			shader.SetVec("DiffuseLight", diffuse, 3);
			shader.SetVec("Eye", camera.Eye.X, camera.Eye.Y, camera.Eye.Z);
			shader.SetVec("HazeRange", camera.HazeRange.X, camera.HazeRange.Y);
			shader.SetVec("SkyColour", camera.SkyColour, 3);
			shader.SetTexture("Atlas", atlas.GetTexture());
			shader.SetTexture("Instances", instances);

			foreach (var (model, x, z, yaw, mirror) in placements)
			{
				var m = models[model];
				if (!Visible(camera, m.Min, m.Max, x, z, yaw, mirror))
					continue;

				shader.SetVec("Placement", x, z, yaw);
				shader.SetVec("Mirror", mirror);
				foreach (var (mesh, first, count) in m.Batches)
				{
					shader.SetVec("InstanceBase", first);
					shader.PrepareRender();
					Game.Renderer.DrawBatchInstanced(vertices, shader, meshes[mesh].First, meshes[mesh].Count, count, PrimitiveType.TriangleList);
				}
			}
		}

		/// <summary>
		/// False when the placed model's box lies entirely beyond one clip plane. Conservative: a box that
		/// straddles planes is drawn.
		/// </summary>
		static bool Visible(Camera3D camera, float3 min, float3 max, float x, float z, float yaw, float mirror)
		{
			// Past the end of the haze everything is sky colour: skip what lies wholly beyond it.
			var half = new float2(max.X - min.X, max.Z - min.Z).Length / 2 + Math.Max(Math.Abs(max.Y), Math.Abs(min.Y));
			var d = new float3(x, (min.Y + max.Y) / 2, z) - camera.Eye;
			if ((float)Math.Sqrt(d.X * d.X + d.Y * d.Y + d.Z * d.Z) - half > camera.HazeRange.Y)
				return false;

			var vp = camera.ViewProjection;
			float c = (float)Math.Cos(yaw), s = (float)Math.Sin(yaw);
			Span<int> outside = stackalloc int[6];
			for (var k = 0; k < 8; k++)
			{
				var px = ((k & 1) == 0 ? min.X : max.X) * mirror;
				var py = (k & 2) == 0 ? min.Y : max.Y;
				var pz = (k & 4) == 0 ? min.Z : max.Z;
				var wx = c * px + s * pz + x;
				var wz = -s * px + c * pz + z;
				var cx = vp[0] * wx + vp[4] * py + vp[8] * wz + vp[12];
				var cy = vp[1] * wx + vp[5] * py + vp[9] * wz + vp[13];
				var cz = vp[2] * wx + vp[6] * py + vp[10] * wz + vp[14];
				var cw = vp[3] * wx + vp[7] * py + vp[11] * wz + vp[15];
				if (cx < -cw) outside[0]++;
				if (cx > cw) outside[1]++;
				if (cy < -cw) outside[2]++;
				if (cy > cw) outside[3]++;
				if (cz < -cw) outside[4]++;
				if (cz > cw) outside[5]++;
			}

			foreach (var n in outside)
				if (n == 8)
					return false;

			return true;
		}

		public void Dispose()
		{
			vertices.Dispose();
			instances.Dispose();
			atlas.Dispose();
		}
	}
}
