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

using System;
using OpenRA.Primitives;

namespace OpenRA.Graphics
{
	/// <summary>
	/// Switch and tuning for the perspective RTS camera (mod.yaml `PerspectiveCamera:`). Lengths are metres,
	/// angles degrees. The defaults are the Godot camera in game-studio/src/camera/rts_camera.gd, which
	/// <see cref="Camera3D"/> copies.
	/// </summary>
	public class PerspectiveCamera : IGlobalModData
	{
		public readonly bool Enabled = false;

		[Desc("World scale: how many metres one map cell stands for.")]
		public readonly float MetresPerCell = 8f;

		public readonly float MinAltitude = 60f;
		public readonly float MaxAltitude = 700f;

		[Desc("Altitude change per wheel notch = ScrollStep x a factor that goes from ScrollFactorLow at the ground to ScrollFactorHigh at ScrollFactorAltitude.")]
		public readonly float ScrollStep = 300f;
		public readonly float ScrollFactorLow = 0.1f;
		public readonly float ScrollFactorHigh = 0.22f;
		public readonly float ScrollFactorAltitude = 130f;

		[Desc("Altitude smoothing and wheel inertia decay, 1/s.")]
		public readonly float AltitudeRate = 5f;
		public readonly float ScrollDamping = 4.5f;

		[Desc("Planar speed in m/s at altitude 0 and at SpeedAltitude, linear in between.")]
		public readonly float SpeedAtGround = 10f;
		public readonly float SpeedAtAltitude = 2000f;
		public readonly float SpeedAltitude = 600f;
		public readonly float FastMultiplier = 3f;

		[Desc("Pan velocity decay after the keys are released, and target smoothing, 1/s.")]
		public readonly float Damping = 8f;
		public readonly float FollowRate = 10f;

		public readonly float YawPerPixel = 0.33f;
		public readonly float KeyYawSpeed = 90f;

		[Desc("Pitch below the horizon at MinAltitude and MaxAltitude, and its per-frame (60 fps) lerp factor.")]
		public readonly float PitchLow = 25f;
		public readonly float PitchHigh = 60f;
		public readonly float PitchLerp = 0.15f;

		[Desc("Roof collision: the eye stays RoofClearance above any roof within CollisionRadius, easing up at LiftRate (1/s).")]
		public readonly float RoofClearance = 6f;
		public readonly float CollisionRadius = 8f;
		public readonly float LiftRate = 12f;

		[Desc("Distance haze: starts at HazeBegin x and is full at HazeEnd x the view distance, never closer than",
			"HazeMinBegin / HazeMinEnd metres, so the map centre stays clear at every altitude. SkyColour is the haze and the sky.")]
		public readonly float HazeBegin = 1.2f;
		public readonly float HazeEnd = 3.5f;
		public readonly float HazeMinBegin = 300f;
		public readonly float HazeMinEnd = 1500f;
		public readonly float[] SkyColour = { 0.66f, 0.68f, 0.70f };

		public readonly float Fov = 60f;
		public readonly float Near = 0.5f;
		public readonly float Far = 8000f;

		[Desc("Starting view: yaw, the pitch used to turn StartFraming into an altitude, and the vertical extent framed.")]
		public readonly float StartYaw = 45f;
		public readonly float StartPitch = 35.264f;
		public readonly float StartFraming = 380f;
	}

	/// <summary>
	/// Perspective RTS camera orbiting a point on the world plane. The 2D world (world pixels, x east, y south)
	/// lies on the y = 0 plane of a Godot-style frame: x east, y up, z south. Positions passed in and out are
	/// world pixels; tuning is metres.
	/// </summary>
	public sealed class Camera3D
	{
		readonly PerspectiveCamera s;
		readonly float pxPerMetre;
		readonly float2 min, max;
		readonly float tanHalfFov;

		float2 target, goal, velocity;
		float altitude, altitudeGoal, altitudeVelocity;
		float yaw, pitch;
		bool dragging;
		Size screen;

		float3 eye, right, up, back;
		float lift;

		/// <summary>
		/// Highest roof (world px above the ground) within a radius (world px) of a ground point (world px),
		/// or float.NegativeInfinity over open ground. Set by whatever owns the 3D buildings; null = no collision.
		/// </summary>
		public Func<float2, float, float> RoofHeight { get; set; }

		/// <summary>Column-major view-projection matrix. Its y is flipped so NDC -1 is the top of the screen, as in the 2D world pass.</summary>
		public float[] ViewProjection { get; } = new float[16];

		/// <summary>Ground point the camera orbits, world px.</summary>
		public float2 Target => target;

		/// <summary>The eye in the camera frame (world px: x east, y up, z south).</summary>
		public float3 Eye => eye;

		/// <summary>Haze start and full distance from the eye, world px.</summary>
		public float2 HazeRange { get; private set; }

		public float[] SkyColour => s.SkyColour;

		public Camera3D(PerspectiveCamera settings, float pxPerMetre, Rectangle mapBounds, Size screen)
		{
			s = settings;
			this.pxPerMetre = pxPerMetre;
			min = new float2(mapBounds.Left, mapBounds.Top);
			max = new float2(mapBounds.Right, mapBounds.Bottom);
			this.screen = screen;
			tanHalfFov = (float)Math.Tan(Rad(s.Fov) * 0.5f);

			target = goal = 0.5f * (min + max);
			yaw = s.StartYaw;
			var distance = s.StartFraming * 0.5f / tanHalfFov;
			altitude = altitudeGoal = Math.Clamp(distance * (float)Math.Sin(Rad(s.StartPitch)), s.MinAltitude, s.MaxAltitude);
			pitch = DefaultPitch(altitude);
			Rebuild();
		}

		/// <summary>
		/// Advances one frame. <paramref name="input"/> is the screen-space pan direction (x right, y up) from keys
		/// and screen edges; <paramref name="yawInput"/> is -1 (Q), 0 or +1 (E).
		/// </summary>
		public void Update(float dt, float2 input, bool fast, int yawInput, Size screenSize)
		{
			screen = screenSize;
			if (input != float2.Zero)
				velocity = GroundVector(input / input.Length) * (PlanarSpeed() * (fast ? s.FastMultiplier : 1f) * pxPerMetre);
			else
				velocity *= Decay(s.Damping, dt);

			if (!dragging)
				goal = Clamped(goal + velocity * dt);

			target = float2.Lerp(target, goal, 1f - Decay(s.FollowRate, dt));

			altitudeGoal = Math.Clamp(altitudeGoal + altitudeVelocity * dt, s.MinAltitude, s.MaxAltitude);
			altitudeVelocity *= Decay(s.ScrollDamping, dt);
			altitude = float2.Lerp(altitude, altitudeGoal, 1f - Decay(s.AltitudeRate, dt));

			yaw += yawInput * s.KeyYawSpeed * dt;
			pitch = float2.Lerp(pitch, DefaultPitch(altitude), 1f - (float)Math.Pow(1f - s.PitchLerp, dt * 60f));
			Rebuild(dt);
		}

		/// <summary>One wheel notch: +1 = up (zoom out), -1 = down. Leaves some velocity behind (scroll inertia).</summary>
		public void Scroll(float dir)
		{
			var t = Math.Clamp(altitude / s.ScrollFactorAltitude, 0f, 1f);
			var step = s.ScrollStep * float2.Lerp(s.ScrollFactorLow, s.ScrollFactorHigh, t);
			altitudeGoal = Math.Clamp(altitudeGoal + dir * step, s.MinAltitude, s.MaxAltitude);
			altitudeVelocity += dir * step * s.ScrollDamping * 0.25f;
		}

		public void SetDragging(bool value)
		{
			dragging = value;
			velocity = float2.Zero;
		}

		/// <summary>Middle drag: turns the view by the horizontal mouse movement, in screen px.</summary>
		public void DragYaw(float dx)
		{
			yaw += dx * s.YawPerPixel;
			Rebuild();
		}

		/// <summary>Alt + middle drag: the ground under the cursor follows the mouse (screen px).</summary>
		public void GrabPan(float2 delta)
		{
			var metresPerPx = ViewDistance() * 2f * tanHalfFov / screen.Height;
			goal = Clamped(goal + GroundVector(new float2(-delta.X, delta.Y)) * (metresPerPx * pxPerMetre));
			target = goal;
			Rebuild();
		}

		/// <summary>Jumps to a yaw and a settled altitude, with the pitch that altitude gets.</summary>
		public void SetView(float yawDegrees, float altitudeMetres)
		{
			yaw = yawDegrees;
			altitude = altitudeGoal = Math.Clamp(altitudeMetres, s.MinAltitude, s.MaxAltitude);
			altitudeVelocity = 0;
			pitch = DefaultPitch(altitude);
			Rebuild();
		}

		/// <summary>Jumps to a ground point (world px), as the 2D viewport's Center does.</summary>
		public void CenterOn(float2 ground)
		{
			goal = target = Clamped(ground);
			velocity = float2.Zero;
			Rebuild();
		}

		/// <summary>Moves target and goal together by world px, unclamped, so a caller (screen shake) can undo it exactly.</summary>
		public void Offset(float2 delta)
		{
			goal += delta;
			target += delta;
			Rebuild();
		}

		/// <summary>Pans by a screen-space vector (x right, y down), one world px per screen px at the target.</summary>
		public void PanScreen(float2 delta)
		{
			goal = Clamped(goal + GroundVector(new float2(delta.X, -delta.Y)) / PxScaleAtTarget);
			target = goal;
			Rebuild();
		}

		/// <summary>Screen px per world px at the orbit target.</summary>
		public float PxScaleAtTarget => screen.Height / (2f * ViewDistance() * pxPerMetre * tanHalfFov);

		/// <summary>Projects a world px ground point to screen px. Points behind the eye land far off screen.</summary>
		public float2 Project(float2 world)
		{
			var m = ViewProjection;
			var x = m[0] * world.X + m[8] * world.Y + m[12];
			var y = m[1] * world.X + m[9] * world.Y + m[13];
			var w = m[3] * world.X + m[11] * world.Y + m[15];
			if (w <= 1e-4f)
				return new float2(-1e6f, -1e6f);

			return new float2((x / w + 1f) * 0.5f * screen.Width, (y / w + 1f) * 0.5f * screen.Height);
		}

		/// <summary>Camera axes in the world frame (x east, y up, z south): billboards are spanned by these.</summary>
		public float3 Right => right;
		public float3 Up => up;

		/// <summary>Projects a 3D point (world px: x east, y up, z south) to screen px. Behind the eye lands far off screen.</summary>
		public float2 ProjectPoint(in float3 p)
		{
			var m = ViewProjection;
			var x = m[0] * p.X + m[4] * p.Y + m[8] * p.Z + m[12];
			var y = m[1] * p.X + m[5] * p.Y + m[9] * p.Z + m[13];
			var w = m[3] * p.X + m[7] * p.Y + m[11] * p.Z + m[15];
			if (w <= 1e-4f)
				return new float2(-1e6f, -1e6f);

			return new float2((x / w + 1f) * 0.5f * screen.Width, (y / w + 1f) * 0.5f * screen.Height);
		}

		/// <summary>
		/// The world px ground point under a screen px. A ray at or above the horizon returns the point
		/// Far metres away along its heading, so the result is always on the plane.
		/// </summary>
		public float2 GroundAt(float2 screenPx)
		{
			var nx = 2f * screenPx.X / screen.Width - 1f;
			var ny = 2f * screenPx.Y / screen.Height - 1f;
			var aspect = (float)screen.Width / screen.Height;
			var dir = nx * tanHalfFov * aspect * right - ny * tanHalfFov * up - back;

			var farPx = s.Far * 0.5f * pxPerMetre;
			float3 hit;
			if (dir.Y < -1e-4f)
			{
				var t = -eye.Y / dir.Y;
				hit = eye + t * dir;
				var flat = new float2(hit.X - eye.X, hit.Z - eye.Z);
				if (flat.Length > farPx)
					hit = eye + farPx / flat.Length * new float3(flat.X, 0, flat.Y);
			}
			else
			{
				var flat = new float2(dir.X, dir.Z);
				hit = eye + farPx / Math.Max(flat.Length, 1e-4f) * new float3(flat.X, 0, flat.Y);
			}

			return new float2(hit.X, hit.Z);
		}

		/// <summary>Bounding box (world px) of the ground the screen shows, grown by <paramref name="margin"/>.</summary>
		public Rectangle VisibleGround(int margin)
		{
			var w = screen.Width;
			var h = screen.Height;
			var tl = new float2(float.MaxValue, float.MaxValue);
			var br = new float2(float.MinValue, float.MinValue);
			foreach (var p in new[] { new float2(0, 0), new float2(w, 0), new float2(0, h), new float2(w, h), new float2(w / 2, 0), new float2(w / 2, h) })
			{
				var g = GroundAt(p);
				tl = float2.Min(tl, g);
				br = float2.Max(br, g);
			}

			return Rectangle.FromLTRB((int)tl.X - margin, (int)tl.Y - margin, (int)br.X + margin, (int)br.Y + margin);
		}

		float PlanarSpeed()
		{
			return float2.Lerp(s.SpeedAtGround, s.SpeedAtAltitude, Math.Clamp(altitude / s.SpeedAltitude, 0f, 1f));
		}

		float DefaultPitch(float alt)
		{
			var t = Math.Clamp((alt - s.MinAltitude) / (s.MaxAltitude - s.MinAltitude), 0f, 1f);
			return float2.Lerp(s.PitchLow, s.PitchHigh, t);
		}

		/// <summary>Metres from the eye to the target.</summary>
		float ViewDistance()
		{
			return altitude / (float)Math.Sin(Rad(Math.Clamp(pitch, 5f, 89f)));
		}

		/// <summary>World px ground direction for a screen direction: right = camera right, up = heading.</summary>
		float2 GroundVector(float2 dir)
		{
			var y = Rad(yaw);
			var forward = new float2(-(float)Math.Sin(y), -(float)Math.Cos(y));
			var side = new float2((float)Math.Cos(y), -(float)Math.Sin(y));
			return dir.X * side + dir.Y * forward;
		}

		float2 Clamped(float2 p)
		{
			return new float2(Math.Clamp(p.X, min.X, max.X), Math.Clamp(p.Y, min.Y, max.Y));
		}

		static float Decay(float rate, float dt) { return (float)Math.Exp(-rate * dt); }
		static float Rad(float degrees) { return degrees * (float)Math.PI / 180f; }

		/// <summary>
		/// Godot's Basis.from_euler(-pitch, yaw, 0): columns right, up, back; the eye sits ViewDistance back.
		/// Then rts_camera.gd's roof collision: the eye is lifted above nearby roofs (easing in over
		/// <paramref name="dt"/>, at once when dt is 0 or a tall wall appears) and re-aimed at the target.
		/// </summary>
		void Rebuild(float dt = 0f)
		{
			var p = Rad(pitch);
			var a = Rad(yaw);
			float sp = (float)Math.Sin(p), cp = (float)Math.Cos(p), sa = (float)Math.Sin(a), ca = (float)Math.Cos(a);
			right = new float3(ca, 0, -sa);
			up = new float3(-sp * sa, cp, -sp * ca);
			back = new float3(cp * sa, sp, cp * ca);
			var centre = new float3(target.X, 0, target.Y);
			var distance = ViewDistance();
			eye = centre + distance * pxPerMetre * back;
			HazeRange = pxPerMetre * new float2(Math.Max(distance * s.HazeBegin, s.HazeMinBegin), Math.Max(distance * s.HazeEnd, s.HazeMinEnd));

			if (RoofHeight != null)
			{
				var roof = RoofHeight(new float2(eye.X, eye.Z), s.CollisionRadius * pxPerMetre);
				var need = Math.Max(0f, roof + s.RoofClearance * pxPerMetre - eye.Y);
				if (dt <= 0f || need > lift + 20f * pxPerMetre)
					lift = need;
				else
					lift += (need - lift) * (1f - Decay(s.LiftRate, dt));

				lift = Math.Max(lift, need * 0.999f);
			}
			else
				lift = 0f;

			if (lift > 0.01f)
			{
				eye += new float3(0, lift, 0);
				var d = eye - centre;
				back = (1f / (float)Math.Sqrt(Dot(d, d))) * d;
				var r = new float3(back.Z, 0, -back.X);
				right = (1f / (float)Math.Sqrt(Dot(r, r))) * r;
				up = new float3(back.Y * right.Z, back.Z * right.X - back.X * right.Z, -back.Y * right.X);
			}

			// View: rows right, up, back with translation -R^T * eye. Projection: GL perspective, then y negated.
			var f = 1f / tanHalfFov;
			var aspect = screen.Height > 0 ? (float)screen.Width / screen.Height : 1f;
			var n = s.Near * pxPerMetre;
			var fa = s.Far * pxPerMetre;
			var a22 = (fa + n) / (n - fa);
			var a23 = 2f * fa * n / (n - fa);

			var tx = -Dot(right, eye);
			var ty = -Dot(up, eye);
			var tz = -Dot(back, eye);

			var m = ViewProjection;
			var sx = f / aspect;
			var sy = -f;

			// Column 0..3 = view columns pushed through the projection rows.
			m[0] = sx * right.X; m[1] = sy * up.X; m[2] = a22 * back.X; m[3] = -back.X;
			m[4] = sx * right.Y; m[5] = sy * up.Y; m[6] = a22 * back.Y; m[7] = -back.Y;
			m[8] = sx * right.Z; m[9] = sy * up.Z; m[10] = a22 * back.Z; m[11] = -back.Z;
			m[12] = sx * tx; m[13] = sy * ty; m[14] = a22 * tz + a23; m[15] = -tz;
			UpdateRenderMatrix();
		}

		/// <summary>
		/// ViewProjection as the shaders must use it: the world is drawn into a framebuffer of which only the
		/// screen-sized corner is shown (Renderer.BeginWorld), so clip space is squeezed into that corner.
		/// Project, ProjectPoint and GroundAt keep working in screen terms with ViewProjection.
		/// </summary>
		public float[] RenderViewProjection { get; } = new float[16];

		float2 bufferScale = new(1f, 1f);

		/// <summary>The shown corner's share of the world framebuffer, per axis (Renderer.BeginWorld sets it).</summary>
		public void SetBufferScale(float2 scale)
		{
			if (scale == bufferScale)
				return;

			bufferScale = scale;
			UpdateRenderMatrix();
		}

		// Clip x' = a x + (a - 1) w (likewise y with b): NDC -1..1 becomes -1..2a-1, the shown corner.
		void UpdateRenderMatrix()
		{
			var m = ViewProjection;
			var r = RenderViewProjection;
			float a = bufferScale.X, b = bufferScale.Y;
			for (var c = 0; c < 4; c++)
			{
				var w = m[c * 4 + 3];
				r[c * 4] = a * m[c * 4] + (a - 1f) * w;
				r[c * 4 + 1] = b * m[c * 4 + 1] + (b - 1f) * w;
				r[c * 4 + 2] = m[c * 4 + 2];
				r[c * 4 + 3] = w;
			}
		}

		static float Dot(in float3 a, in float3 b) { return a.X * b.X + a.Y * b.Y + a.Z * b.Z; }
	}
}
