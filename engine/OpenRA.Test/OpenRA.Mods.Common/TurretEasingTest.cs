#region Copyright & License Information
/*
 * Turret traverse with spin-up and braking (Util.TickFacingEased, used by Turreted when TurnSpinUpTicks > 0):
 * a real turret drive ramps up to its rated traverse speed, holds it, and brakes so it stops ON the target
 * without overshooting. Fixed point (1/256 WAngle), so the simulation stays deterministic.
 */
#endregion

using System;
using NUnit.Framework;
using OpenRA.Mods.Common;

namespace OpenRA.Test
{
	[TestFixture]
	public class TurretEasingTest
	{
		const int Fine = Util.FacingFine;

		// T-90 rating: 4 WAngle a tick (23.4 deg/s at 16.67 ticks/s), full speed after 8 ticks.
		const int MaxSpeed = 4 * Fine;
		const int Acceleration = MaxSpeed / 8;

		static (int Ticks, int MaxSeen, int[] Steps) Run(int from, int to)
		{
			var position = from * Fine;
			var speed = 0;
			var maxSeen = 0;
			var steps = new int[400];
			var t = 0;
			for (; t < steps.Length; t++)
			{
				var before = position;
				position = Util.TickFacingEased(position, new WAngle(to), ref speed, MaxSpeed, Acceleration);
				var step = Math.Abs(Delta(before, position));
				steps[t] = step;
				maxSeen = Math.Max(maxSeen, step);
				if (position == to * Fine && speed == 0)
					break;
			}

			return (t + 1, maxSeen, steps);
		}

		static int Delta(int a, int b)
		{
			var d = (b - a) % (1024 * Fine);
			if (d >= 512 * Fine)
				d -= 1024 * Fine;
			else if (d < -512 * Fine)
				d += 1024 * Fine;

			return d;
		}

		[TestCase(0, 256)]
		[TestCase(0, 768)]
		[TestCase(1000, 40)]
		[TestCase(300, 301)]
		public void StopsExactlyOnTheTarget(int from, int to)
		{
			var run = Run(from, to);
			Assert.That(run.Ticks, Is.LessThan(400), "never settled");
		}

		[Test]
		public void NeverExceedsTheRatedSpeed()
		{
			Assert.That(Run(0, 512).MaxSeen, Is.LessThanOrEqualTo(MaxSpeed));
		}

		[Test]
		public void RampsUpAndBrakesInsteadOfJumping()
		{
			var steps = Run(0, 256).Steps;
			Assert.That(steps[0], Is.LessThanOrEqualTo(Acceleration), "first tick starts at full speed");
			Assert.That(steps[1], Is.GreaterThan(steps[0]), "no spin-up");
			Assert.That(steps[3], Is.GreaterThan(steps[1]), "no spin-up");
		}

		[Test]
		public void TakesTheShortWayRound()
		{
			// 1000 -> 40 is 64 WAngle clockwise through 0, not 960 the other way.
			var position = 1000 * Fine;
			var speed = 0;
			position = Util.TickFacingEased(position, new WAngle(40), ref speed, MaxSpeed, Acceleration);
			Assert.That(speed, Is.GreaterThan(0));
		}

		[Test]
		public void QuarterTurnTakesRoughlyTheRatedTime()
		{
			// 90 degrees at 23.4 deg/s is 3.85 s = 64 ticks at full speed; spin-up and braking add about 8.
			var ticks = Run(0, 256).Ticks;
			Assert.That(ticks, Is.InRange(64, 80));
		}
	}
}
