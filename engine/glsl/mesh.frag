#version {VERSION}
#ifdef GL_ES
precision highp float;
precision highp int;
#endif

// Facades: an atlas of AtlasGrid x AtlasGrid tiles, style s at column s % grid, rows 2(s / grid) (upper
// floors, tiles both ways) and the row below it (ground floor, tiles horizontally). StyleTable holds
// (width, upper height, ground height) in metres per style. Roofs: one image over the map square.
uniform sampler2D Facades;
uniform sampler2D Roofs;
uniform sampler2D StyleTable;
uniform float AtlasGrid;

// Distance haze, as in the world sprite shader.
uniform vec3 Eye;
uniform vec2 HazeRange;
uniform vec3 SkyColour;
in vec3 vWorld;

// Ground surfaces (style 100 + k): a second atlas of AtlasGrid x AtlasGrid seamless tiles, tile k at
// (k % grid, k / grid), each covering SurfaceTable[k].x metres; vTexCoord is in metres.
uniform sampler2D Surfaces;
uniform sampler2D SurfaceTable;

in vec3 vTint;
in vec3 vLight;
in vec2 vTexCoord;
flat in float vStyle;

out vec4 fragColor;

void main()
{
	vec3 albedo;
	if (vStyle > 99.5)
	{
		int k = int(vStyle - 100.0 + 0.5);
		int grid = int(AtlasGrid);
		vec2 cont = vTexCoord / texelFetch(SurfaceTable, ivec2(k, 0), 0).x;
		float inset = 0.5 * AtlasGrid / float(textureSize(Surfaces, 0).x);
		vec2 local = clamp(fract(cont), inset, 1.0 - inset);
		vec2 tile = vec2(float(k % grid), float(k / grid));
		vec2 g = cont / AtlasGrid;
		albedo = textureGrad(Surfaces, (tile + local) / AtlasGrid, dFdx(g), dFdy(g)).rgb * vTint;
	}
	else if (vStyle < -1.5)
		albedo = vTint;
	else if (vStyle < -0.5)
		albedo = texture(Roofs, vTexCoord).rgb;
	else
	{
		int s = int(vStyle + 0.5);
		int grid = int(AtlasGrid);
		vec3 size = texelFetch(StyleTable, ivec2(s, 0), 0).xyz;
		bool ground = vTexCoord.y < size.z;
		vec2 cont = vec2(vTexCoord.x / size.x, ground ? vTexCoord.y / size.z : (vTexCoord.y - size.z) / size.y);
		vec2 local = vec2(fract(cont.x), ground ? clamp(cont.y, 0.0, 1.0) : fract(cont.y));

		// Image rows run top-down; facade v runs up. A half-texel inset keeps bilinear taps inside the
		// tile, and the gradients of the unwrapped coordinate stop fract() seams from picking the smallest mip.
		float inset = 0.5 * AtlasGrid / float(textureSize(Facades, 0).x);
		local = clamp(vec2(local.x, 1.0 - local.y), inset, 1.0 - inset);
		vec2 tile = vec2(float(s % grid), float((s / grid) * 2 + (ground ? 1 : 0)));
		vec2 g = cont / AtlasGrid;
		albedo = textureGrad(Facades, (tile + local) / AtlasGrid, dFdx(g), dFdy(g)).rgb * vTint;
	}

	vec3 lit = albedo * vLight;
	fragColor = vec4(mix(lit, SkyColour, smoothstep(HazeRange.x, HazeRange.y, distance(vWorld, Eye))), 1.0);
}
