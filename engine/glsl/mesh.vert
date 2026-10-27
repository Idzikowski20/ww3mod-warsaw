#version {VERSION}

// Flat-shaded 3D meshes for the perspective camera (Graphics/Camera3D.cs, Traits/World/CityMap.cs).
uniform mat4 ViewProjection;
uniform vec3 LightDirection;
uniform vec3 AmbientLight, DiffuseLight;

in vec3 aVertexPosition;
in vec3 aVertexNormal;
in vec3 aVertexColor;

out vec3 vColor;

void main()
{
	gl_Position = ViewProjection * vec4(aVertexPosition, 1.0);
	float lambert = max(dot(aVertexNormal, LightDirection), 0.0);
	vColor = aVertexColor * (AmbientLight + DiffuseLight * lambert);
}
