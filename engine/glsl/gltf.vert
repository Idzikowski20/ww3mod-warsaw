#version {VERSION}

// glTF unit models in the perspective world pass (Graphics/GltfModel.cs): world px, x east / y up / z south.
uniform mat4 ViewProjection;
uniform mat4 Model;

in vec3 aVertexPosition;
in vec3 aVertexNormal;
in vec2 aVertexTexCoord;
in vec4 aVertexColor;

out vec3 vNormal;
out vec2 vTexCoord;
out vec4 vColor;
out vec3 vWorld;

void main()
{
	vec4 world = Model * vec4(aVertexPosition, 1.0);
	vWorld = world.xyz;
	gl_Position = ViewProjection * world;
	vNormal = mat3(Model) * aVertexNormal;
	vTexCoord = aVertexTexCoord;
	vColor = aVertexColor;
}
