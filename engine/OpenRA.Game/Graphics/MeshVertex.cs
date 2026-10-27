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
	/// <summary>A flat-shaded mesh vertex in the perspective camera's frame (world px: x east, y up, z south).</summary>
	[StructLayout(LayoutKind.Sequential)]
	public readonly struct MeshVertex
	{
		public readonly float X, Y, Z;
		public readonly float NX, NY, NZ;
		public readonly float R, G, B;

		public MeshVertex(float x, float y, float z, float nx, float ny, float nz, float r, float g, float b)
		{
			X = x; Y = y; Z = z;
			NX = nx; NY = ny; NZ = nz;
			R = r; G = g; B = b;
		}
	}

	public sealed class MeshShaderBindings : ShaderBindings
	{
		public MeshShaderBindings()
			: base("mesh") { }

		public override ShaderVertexAttribute[] Attributes { get; } = new[]
		{
			new ShaderVertexAttribute("aVertexPosition", ShaderVertexAttributeType.Float, 3, 0),
			new ShaderVertexAttribute("aVertexNormal", ShaderVertexAttributeType.Float, 3, 12),
			new ShaderVertexAttribute("aVertexColor", ShaderVertexAttributeType.Float, 3, 24),
		};
	}
}
