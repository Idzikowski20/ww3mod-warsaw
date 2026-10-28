#version {VERSION}
#ifdef GL_ES
precision mediump float;
#endif

// Fast approximate anti-aliasing (after Timothy Lottes' FXAA, the compact "console" variant): finds
// luminance edges in the finished world image and blends across them, smoothing the stair-stepped edges
// of the 3D models and the city without the cost of multisampling. Reads the world buffer snapshot.
uniform sampler2D WorldTexture;
out vec4 fragColor;

const float ReduceMin = 1.0 / 128.0;
const float ReduceMul = 1.0 / 8.0;
const float SpanMax = 8.0;

float Luma(vec3 c)
{
	return dot(c, vec3(0.299, 0.587, 0.114));
}

void main()
{
	vec2 size = vec2(textureSize(WorldTexture, 0));
	vec2 px = 1.0 / size;
	vec2 uv = gl_FragCoord.xy * px;

	vec3 nw = texture(WorldTexture, uv + vec2(-1.0, -1.0) * px).rgb;
	vec3 ne = texture(WorldTexture, uv + vec2(1.0, -1.0) * px).rgb;
	vec3 sw = texture(WorldTexture, uv + vec2(-1.0, 1.0) * px).rgb;
	vec3 se = texture(WorldTexture, uv + vec2(1.0, 1.0) * px).rgb;
	vec4 m = texture(WorldTexture, uv);

	float lNW = Luma(nw), lNE = Luma(ne), lSW = Luma(sw), lSE = Luma(se), lM = Luma(m.rgb);
	float lMin = min(lM, min(min(lNW, lNE), min(lSW, lSE)));
	float lMax = max(lM, max(max(lNW, lNE), max(lSW, lSE)));

	vec2 dir = vec2(-((lNW + lNE) - (lSW + lSE)), (lNW + lSW) - (lNE + lSE));
	float reduce = max((lNW + lNE + lSW + lSE) * 0.25 * ReduceMul, ReduceMin);
	float rcpMin = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
	dir = clamp(dir * rcpMin, vec2(-SpanMax), vec2(SpanMax)) * px;

	vec3 a = 0.5 * (texture(WorldTexture, uv + dir * (1.0 / 3.0 - 0.5)).rgb
		+ texture(WorldTexture, uv + dir * (2.0 / 3.0 - 0.5)).rgb);
	vec3 b = a * 0.5 + 0.25 * (texture(WorldTexture, uv + dir * -0.5).rgb
		+ texture(WorldTexture, uv + dir * 0.5).rgb);

	float lB = Luma(b);
	fragColor = vec4((lB < lMin || lB > lMax) ? a : b, m.a);
}
