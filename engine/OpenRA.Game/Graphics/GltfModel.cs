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
using System.Linq;
using System.Numerics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using OpenRA.FileFormats;
using OpenRA.Primitives;

namespace OpenRA.Graphics
{
	[StructLayout(LayoutKind.Sequential)]
	public readonly struct GltfVertex
	{
		public readonly float X, Y, Z;
		public readonly float NX, NY, NZ;
		public readonly float U, V;
		public readonly float R, G, B, A;

		public GltfVertex(Vector3 p, Vector3 n, Vector2 uv, Vector4 c)
		{
			X = p.X; Y = p.Y; Z = p.Z;
			NX = n.X; NY = n.Y; NZ = n.Z;
			U = uv.X; V = uv.Y;
			R = c.X; G = c.Y; B = c.Z; A = c.W;
		}
	}

	public sealed class GltfShaderBindings : ShaderBindings
	{
		public GltfShaderBindings()
			: base("gltf")
		{ }

		public override ShaderVertexAttribute[] Attributes { get; } = new[]
		{
			new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 3, 0),
			new ShaderVertexAttribute("aVertexNormal", ShaderVertexAttributeType.Float, 3, 12),
			new ShaderVertexAttribute("aVertexTexCoord", ShaderVertexAttributeType.Float, 2, 24),
			new ShaderVertexAttribute("aVertexColor", ShaderVertexAttributeType.Float, 4, 32),
		};
	}

	/// <summary>
	/// A binary glTF (.glb) model: node hierarchy, triangle meshes with base-colour materials and
	/// optional embedded PNG textures, and node TRS animations. Skinning is not supported: animated
	/// figures are built from rigid parts, each part its own node.
	/// Materials: a name starting "team" is player-coloured (its colour is multiplied by the player
	/// colour), a name starting "outline" is an inverted-hull outline shell.
	/// </summary>
	public sealed class GltfModel
	{
		public sealed class Node
		{
			public string Name;
			public int Parent = -1;
			public Vector3 Translation;
			public Quaternion Rotation = Quaternion.Identity;
			public Vector3 Scale = Vector3.One;
		}

		public readonly struct Part
		{
			public readonly int Node, Start, Count, Texture;
			public readonly bool Outline;

			public Part(int node, int start, int count, int texture, bool outline)
			{
				Node = node; Start = start; Count = count; Texture = texture; Outline = outline;
			}
		}

		public sealed class Channel
		{
			public int Node;
			public string Path;
			public float[] Times;
			public float[] Values;
			public bool Step;
		}

		public sealed class Clip
		{
			public string Name;
			public float Duration;
			public Channel[] Channels;
		}

		public readonly Node[] Nodes;
		public readonly Part[] Parts;
		public readonly Dictionary<string, Clip> Clips;
		public readonly IVertexBuffer<GltfVertex> Vertices;
		public readonly ITexture[] Textures;

		/// <summary>Model-space (glTF metres) box over the rest pose, for mouse bounds.</summary>
		public readonly Vector3 BoundsMin, BoundsMax;

		public GltfModel(Stream s)
		{
			var (json, bin) = ReadGlb(s);
			var root = json.RootElement;

			var nodes = root.GetProperty("nodes");
			Nodes = new Node[nodes.GetArrayLength()];
			for (var i = 0; i < Nodes.Length; i++)
			{
				var n = nodes[i];
				var node = Nodes[i] = new Node { Name = n.TryGetProperty("name", out var name) ? name.GetString() : "" };
				if (n.TryGetProperty("translation", out var t))
					node.Translation = new Vector3(F(t, 0), F(t, 1), F(t, 2));
				if (n.TryGetProperty("rotation", out var r))
					node.Rotation = new Quaternion(F(r, 0), F(r, 1), F(r, 2), F(r, 3));
				if (n.TryGetProperty("scale", out var sc))
					node.Scale = new Vector3(F(sc, 0), F(sc, 1), F(sc, 2));
				if (n.TryGetProperty("matrix", out _))
					throw new InvalidDataException("glTF node matrices are not supported; export TRS.");
			}

			for (var i = 0; i < Nodes.Length; i++)
				if (nodes[i].TryGetProperty("children", out var children))
					foreach (var c in children.EnumerateArray())
						Nodes[c.GetInt32()].Parent = i;

			var textures = new List<ITexture>();
			var images = new Dictionary<int, int>();
			var vertices = new List<GltfVertex>();
			var parts = new List<Part>();
			var materials = root.TryGetProperty("materials", out var m) ? m : default;
			var meshes = root.GetProperty("meshes");
			var pose = WorldMatrices(null, 0, null);
			BoundsMin = new Vector3(float.MaxValue);
			BoundsMax = new Vector3(float.MinValue);

			for (var i = 0; i < Nodes.Length; i++)
			{
				if (!nodes[i].TryGetProperty("mesh", out var meshIndex))
					continue;

				foreach (var prim in meshes[meshIndex.GetInt32()].GetProperty("primitives").EnumerateArray())
				{
					if (prim.TryGetProperty("mode", out var mode) && mode.GetInt32() != 4)
						continue;

					var attr = prim.GetProperty("attributes");
					var pos = Accessor(root, bin, attr.GetProperty("POSITION").GetInt32());
					var nrm = attr.TryGetProperty("NORMAL", out var na) ? Accessor(root, bin, na.GetInt32()) : null;
					var uv = attr.TryGetProperty("TEXCOORD_0", out var ua) ? Accessor(root, bin, ua.GetInt32()) : null;
					var col = attr.TryGetProperty("COLOR_0", out var ca) ? Accessor(root, bin, ca.GetInt32()) : null;
					var count = pos.Length / 3;
					var colorSize = col != null ? col.Length / count : 0;
					var indices = prim.TryGetProperty("indices", out var ia)
						? Accessor(root, bin, ia.GetInt32()).Select(x => (int)x).ToArray()
						: Enumerable.Range(0, count).ToArray();

					var baseColor = Vector4.One;
					var texture = -1;
					var outline = false;
					var team = false;
					if (prim.TryGetProperty("material", out var mi))
					{
						var mat = materials[mi.GetInt32()];
						var matName = mat.TryGetProperty("name", out var mn) ? mn.GetString() : "";
						outline = matName.StartsWith("outline", StringComparison.Ordinal);
						team = matName.StartsWith("team", StringComparison.Ordinal);
						if (mat.TryGetProperty("pbrMetallicRoughness", out var pbr))
						{
							if (pbr.TryGetProperty("baseColorFactor", out var bc))
								baseColor = new Vector4(F(bc, 0), F(bc, 1), F(bc, 2), F(bc, 3));
							if (pbr.TryGetProperty("baseColorTexture", out var bt))
								texture = Texture(root, bin, bt.GetProperty("index").GetInt32(), images, textures);
						}
					}

					parts.Add(new Part(i, vertices.Count, indices.Length, texture, outline));
					foreach (var k in indices)
					{
						var p = new Vector3(pos[3 * k], pos[3 * k + 1], pos[3 * k + 2]);
						var n = nrm != null ? new Vector3(nrm[3 * k], nrm[3 * k + 1], nrm[3 * k + 2]) : Vector3.UnitY;
						var t = uv != null ? new Vector2(uv[2 * k], uv[2 * k + 1]) : Vector2.Zero;
						var c = baseColor;
						if (colorSize >= 3)
							c *= new Vector4(col[colorSize * k], col[colorSize * k + 1], col[colorSize * k + 2], colorSize == 4 ? col[4 * k + 3] : 1f);

						// Team paint is flagged by alpha (see mesh.frag); everything else is opaque.
						c.W = team ? 0f : 1f;
						vertices.Add(new GltfVertex(p, n, t, c));

						if (!outline)
						{
							var w = Vector3.Transform(p, pose[i]);
							BoundsMin = Vector3.Min(BoundsMin, w);
							BoundsMax = Vector3.Max(BoundsMax, w);
						}
					}
				}
			}

			Parts = parts.ToArray();
			Textures = textures.ToArray();
			Vertices = Game.Renderer.CreateVertexBuffer<GltfVertex>(vertices.Count);
			Vertices.SetData(vertices.ToArray(), vertices.Count);

			Clips = new Dictionary<string, Clip>();
			if (root.TryGetProperty("animations", out var anims))
			{
				foreach (var a in anims.EnumerateArray())
				{
					var samplers = a.GetProperty("samplers");
					var channels = new List<Channel>();
					foreach (var ch in a.GetProperty("channels").EnumerateArray())
					{
						var target = ch.GetProperty("target");
						var path = target.GetProperty("path").GetString();
						if (path == "weights" || !target.TryGetProperty("node", out var tn))
							continue;

						var sampler = samplers[ch.GetProperty("sampler").GetInt32()];
						channels.Add(new Channel
						{
							Node = tn.GetInt32(),
							Path = path,
							Times = Accessor(root, bin, sampler.GetProperty("input").GetInt32()),
							Values = Accessor(root, bin, sampler.GetProperty("output").GetInt32()),
							Step = sampler.TryGetProperty("interpolation", out var ip) && ip.GetString() == "STEP"
						});
					}

					var clip = new Clip
					{
						Name = a.TryGetProperty("name", out var an) ? an.GetString() : "",
						Channels = channels.ToArray(),
						Duration = channels.Count > 0 ? channels.Max(c => c.Times[^1]) : 0f
					};

					Clips[clip.Name] = clip;
				}
			}
		}

		/// <summary>
		/// Model-space matrix of every node (System.Numerics row-vector order) for <paramref name="clip"/> at
		/// <paramref name="time"/> seconds, looped. <paramref name="extraYaw"/> adds a turn (radians, about +Y)
		/// to the node of that index after the animation, e.g. a turret following its target.
		/// </summary>
		public Matrix4x4[] WorldMatrices(Clip clip, float time, Dictionary<int, float> extraYaw)
		{
			var t = Nodes.Select(n => n.Translation).ToArray();
			var r = Nodes.Select(n => n.Rotation).ToArray();
			var s = Nodes.Select(n => n.Scale).ToArray();

			if (clip != null && clip.Duration > 0)
			{
				time %= clip.Duration;
				foreach (var c in clip.Channels)
				{
					var (i0, i1, f) = Keys(c, time);
					switch (c.Path)
					{
						case "translation": t[c.Node] = Vector3.Lerp(V3(c.Values, i0), V3(c.Values, i1), f); break;
						case "scale": s[c.Node] = Vector3.Lerp(V3(c.Values, i0), V3(c.Values, i1), f); break;
						case "rotation": r[c.Node] = Quaternion.Slerp(Q(c.Values, i0), Q(c.Values, i1), f); break;
					}
				}
			}

			if (extraYaw != null)
				foreach (var kv in extraYaw)
					r[kv.Key] = Quaternion.CreateFromAxisAngle(Vector3.UnitY, kv.Value) * r[kv.Key];

			// glTF lists parents before children in practice but does not promise it: resolve recursively.
			var world = new Matrix4x4[Nodes.Length];
			var done = new bool[Nodes.Length];
			Matrix4x4 Resolve(int i)
			{
				if (done[i])
					return world[i];

				var local = Matrix4x4.CreateScale(s[i]) * Matrix4x4.CreateFromQuaternion(r[i]) * Matrix4x4.CreateTranslation(t[i]);
				world[i] = Nodes[i].Parent < 0 ? local : local * Resolve(Nodes[i].Parent);
				done[i] = true;
				return world[i];
			}

			for (var i = 0; i < Nodes.Length; i++)
				Resolve(i);

			return world;
		}

		public int NodeIndex(string name) => Array.FindIndex(Nodes, n => n.Name == name);

		static (int, int, float) Keys(Channel c, float time)
		{
			var times = c.Times;
			if (time <= times[0])
				return (0, 0, 0f);

			for (var i = 1; i < times.Length; i++)
			{
				if (time < times[i])
				{
					var f = c.Step ? 0f : (time - times[i - 1]) / (times[i] - times[i - 1]);
					return (i - 1, i, f);
				}
			}

			return (times.Length - 1, times.Length - 1, 0f);
		}

		static Vector3 V3(float[] v, int i) => new(v[3 * i], v[3 * i + 1], v[3 * i + 2]);
		static Quaternion Q(float[] v, int i) => new(v[4 * i], v[4 * i + 1], v[4 * i + 2], v[4 * i + 3]);
		static float F(JsonElement a, int i) => a[i].GetSingle();

		static (JsonDocument, byte[]) ReadGlb(Stream s)
		{
			using var r = new BinaryReader(s);
			if (r.ReadUInt32() != 0x46546C67)
				throw new InvalidDataException("Not a binary glTF (.glb) file.");

			r.ReadUInt32();
			var length = r.ReadUInt32();
			JsonDocument json = null;
			var bin = Array.Empty<byte>();
			var read = 12u;
			while (read < length)
			{
				var chunkLength = r.ReadUInt32();
				var type = r.ReadUInt32();
				var data = r.ReadBytes((int)chunkLength);
				read += 8 + chunkLength;
				if (type == 0x4E4F534A)
					json = JsonDocument.Parse(Encoding.UTF8.GetString(data));
				else if (type == 0x004E4942)
					bin = data;
			}

			return (json, bin);
		}

		static ReadOnlySpan<byte> View(JsonElement root, byte[] bin, int index, out int stride)
		{
			var view = root.GetProperty("bufferViews")[index];
			var offset = view.TryGetProperty("byteOffset", out var o) ? o.GetInt32() : 0;
			stride = view.TryGetProperty("byteStride", out var st) ? st.GetInt32() : 0;
			return bin.AsSpan(offset, view.GetProperty("byteLength").GetInt32());
		}

		/// <summary>Reads an accessor as floats, normalising integer data where the accessor says so.</summary>
		static float[] Accessor(JsonElement root, byte[] bin, int index)
		{
			var a = root.GetProperty("accessors")[index];
			var count = a.GetProperty("count").GetInt32();
			var components = a.GetProperty("type").GetString() switch
			{
				"SCALAR" => 1, "VEC2" => 2, "VEC3" => 3, "VEC4" => 4, "MAT4" => 16,
				var x => throw new InvalidDataException($"Unsupported accessor type {x}")
			};

			var type = a.GetProperty("componentType").GetInt32();
			var size = type switch { 5120 or 5121 => 1, 5122 or 5123 => 2, _ => 4 };
			var normalized = a.TryGetProperty("normalized", out var nz) && nz.GetBoolean();
			var data = View(root, bin, a.GetProperty("bufferView").GetInt32(), out var stride);
			var offset = a.TryGetProperty("byteOffset", out var bo) ? bo.GetInt32() : 0;
			if (stride == 0)
				stride = components * size;

			var ret = new float[count * components];
			for (var i = 0; i < count; i++)
			{
				for (var c = 0; c < components; c++)
				{
					var b = data[(offset + i * stride + c * size)..];
					ret[i * components + c] = type switch
					{
						5126 => BitConverter.ToSingle(b),
						5125 => BitConverter.ToUInt32(b),
						5123 => normalized ? BitConverter.ToUInt16(b) / 65535f : BitConverter.ToUInt16(b),
						5121 => normalized ? b[0] / 255f : b[0],
						5122 => normalized ? Math.Max(BitConverter.ToInt16(b) / 32767f, -1f) : BitConverter.ToInt16(b),
						5120 => normalized ? Math.Max((sbyte)b[0] / 127f, -1f) : (sbyte)b[0],
						_ => throw new InvalidDataException($"Unsupported component type {type}")
					};
				}
			}

			return ret;
		}

		static int Texture(JsonElement root, byte[] bin, int textureIndex, Dictionary<int, int> images, List<ITexture> textures)
		{
			var image = root.GetProperty("textures")[textureIndex].GetProperty("source").GetInt32();
			if (images.TryGetValue(image, out var existing))
				return existing;

			var view = root.GetProperty("images")[image].GetProperty("bufferView").GetInt32();
			var png = new Png(new MemoryStream(View(root, bin, view, out _).ToArray()));
			var bgra = new byte[png.Width * png.Height * 4];
			var stride = png.PixelStride;
			for (var i = 0; i < png.Width * png.Height; i++)
			{
				if (png.Type == SpriteFrameType.Indexed8)
				{
					var c = png.Palette[png.Data[i]];
					bgra[4 * i] = c.B; bgra[4 * i + 1] = c.G; bgra[4 * i + 2] = c.R; bgra[4 * i + 3] = c.A;
					continue;
				}

				bgra[4 * i] = png.Data[stride * i + 2];
				bgra[4 * i + 1] = png.Data[stride * i + 1];
				bgra[4 * i + 2] = png.Data[stride * i];
				bgra[4 * i + 3] = stride == 4 ? png.Data[stride * i + 3] : (byte)255;
			}

			var texture = Game.Renderer.Context.CreateTexture();
			texture.ScaleFilter = TextureScaleFilter.Linear;
			texture.SetData(bgra, png.Width, png.Height);
			textures.Add(texture);
			images[image] = textures.Count - 1;
			return textures.Count - 1;
		}

		// ponytail: one process-wide cache, never freed; models are few and small. Move it onto ModData if
		// mods ever hot-swap or the set grows past what fits in VRAM at once.
		static readonly Dictionary<string, GltfModel> Cache = new();
		static IShader shader;

		public static GltfModel Get(string filename)
		{
			if (!Cache.TryGetValue(filename, out var mesh))
				using (var s = Game.ModData.DefaultFileSystem.Open(filename))
					Cache[filename] = mesh = new GltfModel(s);

			return mesh;
		}

		internal static IShader Shader
		{
			get
			{
				if (shader == null)
				{
					shader = Game.Renderer.CreateShader(new GltfShaderBindings());

					// Sun from the south-east, high, matching the map's baked lighting.
					var light = Vector3.Normalize(new Vector3(0.4f, 1f, 0.5f));
					shader.SetVec("LightDirection", light.X, light.Y, light.Z);
					shader.SetVec("AmbientLight", 0.55f, 0.55f, 0.58f);
					shader.SetVec("DiffuseLight", 0.55f, 0.53f, 0.5f);
					shader.SetBool("FrontIsBack", true);
				}

				return shader;
			}
		}
	}

	/// <summary>One mesh draw in the world pass: <see cref="Mesh"/> posed by a model matrix and node matrices.</summary>
	public sealed class GltfRenderable : IRenderable, IFinalizedRenderable
	{
		readonly GltfModel mesh;
		readonly Matrix4x4 model;
		readonly Matrix4x4[] nodes;
		readonly Color teamColor;

		public GltfRenderable(GltfModel mesh, WPos pos, Matrix4x4 model, Matrix4x4[] nodes, Color teamColor)
		{
			this.mesh = mesh;
			Pos = pos;
			this.model = model;
			this.nodes = nodes;
			this.teamColor = teamColor;
		}

		public WPos Pos { get; }
		public int ZOffset => 0;
		public bool IsDecoration => false;

		public IRenderable WithZOffset(int newOffset) => this;
		public IRenderable OffsetBy(in WVec offset) => new GltfRenderable(mesh, Pos + offset, model, nodes, teamColor);
		public IRenderable AsDecoration() => this;
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) => this;

		public void Render(WorldRenderer wr)
		{
			var camera = wr.Viewport.Camera;
			if (camera == null)
				return;

			// Finish the sprite batch first: the mesh draw binds its own shader and buffer. Models write depth,
			// the flat sprites drawn around them do not (WorldRenderer.Draw).
			Game.Renderer.Flush();
			Game.Renderer.Context.SetDepthWrite(true);
			var shader = GltfModel.Shader;
			shader.SetMatrix("ViewProjection", (float[])camera.RenderViewProjection.Clone());
			shader.SetVec("Eye", camera.Eye.X, camera.Eye.Y, camera.Eye.Z);
			shader.SetVec("HazeRange", camera.HazeRange.X, camera.HazeRange.Y);
			shader.SetVec("SkyColour", camera.SkyColour, 3);
			shader.SetVec("TeamColor", teamColor.R / 255f, teamColor.G / 255f, teamColor.B / 255f);

			foreach (var part in mesh.Parts)
			{
				var m = nodes[part.Node] * model;
				shader.SetMatrix("Model", new[]
				{
					m.M11, m.M12, m.M13, m.M14, m.M21, m.M22, m.M23, m.M24,
					m.M31, m.M32, m.M33, m.M34, m.M41, m.M42, m.M43, m.M44
				});
				shader.SetBool("Outline", part.Outline);
				shader.SetBool("UseTexture", part.Texture >= 0);
				if (part.Texture >= 0)
					shader.SetTexture("DiffuseTexture", mesh.Textures[part.Texture]);

				// Textures are bound here, not by SetTexture.
				shader.PrepareRender();
				Game.Renderer.DrawBatch(mesh.Vertices, shader, part.Start, part.Count, PrimitiveType.TriangleList);
			}

			Game.Renderer.Context.SetDepthWrite(false);
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }

		public Rectangle ScreenBounds(WorldRenderer wr) => Rectangle.Empty;
	}
}
