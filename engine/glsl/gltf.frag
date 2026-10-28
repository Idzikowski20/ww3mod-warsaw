#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D DiffuseTexture;
uniform bool UseTexture;
uniform vec3 TeamColor;
uniform vec3 LightDirection;
uniform vec3 AmbientLight, DiffuseLight;

// Outline shell (a material named "outline*": the mesh solidified outward with flipped normals).
// Only its inside is drawn, so it shows as a dark rim round the silhouette. FrontIsBack flips
// gl_FrontFacing, because the camera's projection mirrors y.
uniform bool Outline;
uniform bool FrontIsBack;

in vec3 vNormal;
in vec2 vTexCoord;
in vec4 vColor;
in vec3 vWorld;

// Distance haze, as the world sprites and city meshes have it (combined.frag).
uniform vec3 Eye;
uniform vec2 HazeRange;
uniform vec3 SkyColour;
out vec4 fragColor;

void main()
{
	if (Outline)
	{
		if (gl_FrontFacing == FrontIsBack)
			discard;

		fragColor = vec4(mix(vColor.rgb, SkyColour, smoothstep(HazeRange.x, HazeRange.y, distance(vWorld, Eye))), 1.0);
		return;
	}

	vec4 c = vColor;
	if (UseTexture)
		c *= texture(DiffuseTexture, vTexCoord);

	// Alpha below 0.5 marks player-colour paint: the colour is a shade multiplied by the team colour.
	vec3 albedo = c.a < 0.5 ? c.rgb * TeamColor : c.rgb;
	float lambert = max(dot(normalize(vNormal), LightDirection), 0.0);
	vec3 lit = albedo * (AmbientLight + DiffuseLight * lambert);
	fragColor = vec4(mix(lit, SkyColour, smoothstep(HazeRange.x, HazeRange.y, distance(vWorld, Eye))), 1.0);
}
