#version {VERSION}

// Placed city models (Traits/World/CityScene.cs), drawn per mesh with instancing. Instance i is four RGBA32F
// texels of Instances at ((i % w) * 4, i / w), w = width / 4: the rows of a 3x4 matrix taking the mesh into
// its model (world px). The model is then placed: Placement = (x, z world px, yaw radians); Mirror = -1 flips x.
uniform mat4 ViewProjection;
uniform vec3 LightDirection;
uniform vec3 AmbientLight, DiffuseLight;
uniform vec3 Placement;
uniform float Mirror;
uniform sampler2D Instances;
uniform float InstanceBase;

in vec3 aVertexPosition;
in vec3 aVertexNormal;
in vec2 aVertexTexCoord;
in vec4 aVertexRect;

out vec3 vLight;
out vec2 vTexCoord;
out vec3 vWorld;
flat out vec4 vRect;

void main()
{
	int i = int(InstanceBase + 0.5) + gl_InstanceID;
	int w = textureSize(Instances, 0).x / 4;
	ivec2 t = ivec2((i % w) * 4, i / w);
	vec4 r0 = texelFetch(Instances, t, 0);
	vec4 r1 = texelFetch(Instances, t + ivec2(1, 0), 0);
	vec4 r2 = texelFetch(Instances, t + ivec2(2, 0), 0);
	vec3 p = vec3(dot(r0.xyz, aVertexPosition) + r0.w, dot(r1.xyz, aVertexPosition) + r1.w, dot(r2.xyz, aVertexPosition) + r2.w);
	vec3 n = normalize(vec3(dot(r0.xyz, aVertexNormal), dot(r1.xyz, aVertexNormal), dot(r2.xyz, aVertexNormal)));

	float c = cos(Placement.z);
	float s = sin(Placement.z);
	p.x *= Mirror;
	n.x *= Mirror;
	vWorld = vec3(c * p.x + s * p.z + Placement.x, p.y, -s * p.x + c * p.z + Placement.y);
	n = vec3(c * n.x + s * n.z, n.y, -s * n.x + c * n.z);
	gl_Position = ViewProjection * vec4(vWorld, 1.0);

	// Two-sided lighting: the kit's thin parts (fences, leaves) are single planes seen from both sides.
	vLight = AmbientLight + DiffuseLight * abs(dot(n, LightDirection));
	vTexCoord = aVertexTexCoord;
	vRect = aVertexRect;
}
