#region Copyright & License Information
/*
 * Perspective camera (Graphics/Camera3D.cs): the ray the mouse casts and the matrix the shader draws with must
 * agree, or a click lands on a different cell than the one under the cursor. Project uses ViewProjection (the
 * same matrix combined.vert draws with); GroundAt builds the ray from the camera basis. A screen point sent
 * to the ground and back must come back to itself at every yaw and altitude.
 */
#endregion

using NUnit.Framework;
using OpenRA.Graphics;
using OpenRA.Primitives;

namespace OpenRA.Test
{
	[TestFixture]
	public class Camera3DTest
	{
		static readonly Size Screen = new(2400, 1350);

		// A 128x128 map at 24 px per cell, 3 px per metre (8 m cells).
		static Camera3D Make()
		{
			return new Camera3D(new PerspectiveCamera(), 3f, new Rectangle(0, 0, 3072, 3072), Screen);
		}

		// Lower two thirds only: at 60 m the top rows look past the Far clamp toward the horizon.
		static readonly float2[] Points =
		{
			new(1200, 675), new(0, 1350), new(2400, 1350), new(150, 600), new(2250, 900), new(1200, 1349)
		};

		[TestCase(0f, 60f)]
		[TestCase(45f, 190f)]
		[TestCase(137f, 400f)]
		[TestCase(270f, 700f)]
		public void GroundAtAndProjectRoundTrip(float yaw, float altitude)
		{
			var camera = Make();
			camera.SetView(yaw, altitude);
			foreach (var p in Points)
			{
				var back = camera.Project(camera.GroundAt(p));
				Assert.That((back - p).Length, Is.LessThan(0.5f), $"screen {p} -> ground {camera.GroundAt(p)} -> screen {back}");
			}
		}

		[Test]
		public void ScreenCentreLooksAtTheTarget()
		{
			var camera = Make();
			Assert.That((camera.GroundAt(new float2(1200, 675)) - camera.Target).Length, Is.LessThan(0.5f));
		}

		[Test]
		public void RoofCollisionLiftsTheEyeAndKeepsAimingAtTheTarget()
		{
			// A 300 m tower (900 px) everywhere: at 120 m the eye must rise above it, still looking at the target.
			var camera = Make();
			camera.RoofHeight = (ground, radius) => 900f;
			camera.SetView(30f, 120f);
			Assert.That((camera.GroundAt(new float2(1200, 675)) - camera.Target).Length, Is.LessThan(0.5f));
			var back = camera.Project(camera.GroundAt(new float2(300, 1200)));
			Assert.That((back - new float2(300, 1200)).Length, Is.LessThan(0.5f));
		}

		[Test]
		public void YawZeroLooksNorth()
		{
			// Screen top is farther north (smaller world y) than the screen bottom; screen right is east.
			var camera = Make();
			camera.SetView(0f, 300f);
			var top = camera.GroundAt(new float2(1200, 500));
			var bottom = camera.GroundAt(new float2(1200, 1300));
			var right = camera.GroundAt(new float2(2300, 675));
			Assert.That(top.Y, Is.LessThan(bottom.Y));
			Assert.That(right.X, Is.GreaterThan(camera.Target.X));
		}
	}
}
