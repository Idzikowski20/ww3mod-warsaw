#version {VERSION}

// Textured 3D meshes for the perspective camera (Graphics/Camera3D.cs, Traits/World/CityMap.cs).
uniform mat4 ViewProjection;
uniform vec3 LightDirection;
uniform vec3 AmbientLight, DiffuseLight;

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
	vWorld = aVertexPosition;
	gl_Position = ViewProjection * vec4(aVertexPosition, 1.0);
	float lambert = max(dot(aVertexNormal, LightDirection), 0.0);
	vLight = AmbientLight + DiffuseLight * lambert;
	vTint = aVertexColor;
	vTexCoord = aVertexTexCoord;
	vStyle = aVertexStyle;
}
