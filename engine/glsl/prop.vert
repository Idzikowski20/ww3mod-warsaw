#version {VERSION}

// Instanced street props (CityMap): one model in the vertex buffer, drawn once per instance. Instance i
// is two RGBA32F texels of Instances at ((i % w) * 2, i / w), w = width / 2:
//   (x, z world px, yaw radians, scale) and (tint r, g, b, -).
// Vertices with style -3 take the tint (car paint, tree crowns); all are drawn as plain colour (-2).
uniform mat4 ViewProjection;
uniform vec3 LightDirection;
uniform vec3 AmbientLight, DiffuseLight;
uniform sampler2D Instances;
uniform float InstanceBase;

in vec3 aVertexPosition;
in vec3 aVertexNormal;
in vec3 aVertexColor;
in vec2 aVertexTexCoord;
in float aVertexStyle;

out vec3 vTint;
out vec3 vLight;
out vec2 vTexCoord;
out vec3 vWorld;
flat out float vStyle;

void main()
{
	int i = int(InstanceBase + 0.5) + gl_InstanceID;
	int w = textureSize(Instances, 0).x / 2;
	ivec2 t = ivec2((i % w) * 2, i / w);
	vec4 a = texelFetch(Instances, t, 0);
	vec4 b = texelFetch(Instances, t + ivec2(1, 0), 0);

	float c = cos(a.z);
	float s = sin(a.z);
	vec3 p = aVertexPosition * a.w;
	p = vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z) + vec3(a.x, 0.0, a.y);
	vec3 n = vec3(c * aVertexNormal.x + s * aVertexNormal.z, aVertexNormal.y, -s * aVertexNormal.x + c * aVertexNormal.z);

	vWorld = p;
	gl_Position = ViewProjection * vec4(p, 1.0);
	vLight = AmbientLight + DiffuseLight * max(dot(n, LightDirection), 0.0);
	vTint = aVertexStyle < -2.5 ? aVertexColor * b.rgb : aVertexColor;
	vTexCoord = vec2(0.0);
	vStyle = -2.0;
}
