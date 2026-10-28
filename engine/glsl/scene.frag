#version {VERSION}
#ifdef GL_ES
precision highp float;
#endif

// Atlas of the models' base-colour images: each vertex carries its image's rectangle (x, y, w, h in atlas
// UV); the model UV repeats inside it. Alpha below 0.5 is a cut-out (leaves, fences).
uniform sampler2D Atlas;
uniform vec3 Eye;
uniform vec2 HazeRange;
uniform vec3 SkyColour;

in vec3 vLight;
in vec2 vTexCoord;
in vec3 vWorld;
flat in vec4 vRect;

out vec4 fragColor;

void main()
{
	vec2 size = vec2(textureSize(Atlas, 0));
	vec2 inset = 0.5 / size;
	vec2 local = fract(vec2(vTexCoord.x, 1.0 - vTexCoord.y));
	vec2 uv = vRect.xy + clamp(local * vRect.zw, inset, vRect.zw - inset);
	vec2 g = vec2(vTexCoord.x, -vTexCoord.y) * vRect.zw;
	vec4 albedo = textureGrad(Atlas, uv, dFdx(g), dFdy(g));
	if (albedo.a < 0.5)
		discard;

	vec3 lit = albedo.rgb * vLight;
	fragColor = vec4(mix(lit, SkyColour, smoothstep(HazeRange.x, HazeRange.y, distance(vWorld, Eye))), 1.0);
}
