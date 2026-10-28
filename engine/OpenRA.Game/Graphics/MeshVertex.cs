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

using System.Runtime.InteropServices;

namespace OpenRA.Graphics
{
	/// <summary>
	/// A mesh vertex in the perspective camera's frame (world px: x east, y up, z south). Style selects the
	/// surface: >= 0 a facade atlas style (U, V = metres along the wall and above the base, RGB = tint),
	/// -1 the roof image (U, V = its texture coordinates), -2 the plain RGB colour.
	/// </summary>
	[StructLayout(LayoutKind.Sequential)]
	public readonly struct MeshVertex
	{
		public readonly float X, Y, Z;
		public readonly float NX, NY, NZ;
		public readonly float R, G, B;
		public readonly float U, V;
		public readonly float Style;

		public MeshVertex(float x, float y, float z, float nx, float ny, float nz, float r, float g, float b, float u, float v, float style)
		{
			X = x; Y = y; Z = z;
			NX = nx; NY = ny; NZ = nz;
			R = r; G = g; B = b;
			U = u; V = v;
			Style = style;
		}
	}

	public class MeshShaderBindings : ShaderBindings
	{
		public MeshShaderBindings()
			: base("mesh") { }

		protected MeshShaderBindings(string vertexName, string fragmentName)
			: base(vertexName, fragmentName) { }

		public override ShaderVertexAttribute[] Attributes { get; } = new[]
		{
			new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 3, 0),
			new ShaderVertexAttribute("aVertexNormal", ShaderVertexAttributeType.Float, 3, 12),
			new ShaderVertexAttribute("aVertexColor", ShaderVertexAttributeType.Float, 3, 24),
			new ShaderVertexAttribute("aVertexTexCoord", ShaderVertexAttributeType.Float, 2, 36),
			new ShaderVertexAttribute("aVertexStyle", ShaderVertexAttributeType.Float, 1, 44),
		};
	}

	/// <summary>Instanced props: the mesh vertex layout, positioned per instance by prop.vert.</summary>
	public sealed class PropShaderBindings : MeshShaderBindings
	{
		public PropShaderBindings()
			: base("prop", "mesh") { }
	}
}
