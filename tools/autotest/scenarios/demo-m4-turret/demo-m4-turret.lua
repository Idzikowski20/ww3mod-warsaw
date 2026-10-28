-- DEMO: the T-90 faces north; the Abrams (holding fire, unkillable) sits due west. On the order the
-- turret must spin up, traverse 90 degrees left at ~23 deg/s and brake onto the target: about 4 s.
WorldLoaded = function()
	UnitA.Stance = "HoldFire"
	UnitB.Stance = "HoldFire"
	TestHarness.FocusBetween(UnitB)
	Camera.SetView(0, 60)
	TestHarness.ScreenshotAfter(1, "00-start", "expects: turret forward (north, up the screen)")
	Trigger.AfterDelay(TestHarness.TicksForSeconds(1.2), function() UnitB.Attack(UnitA, true, true) end)
	for i, s in ipairs({ 1.8, 2.4, 3.0, 3.6, 4.2, 4.8, 5.6, 6.0, 6.2, 6.4, 6.6, 6.8, 7.0, 7.4, 7.8, 8.2, 8.6, 9.0 }) do
		TestHarness.ScreenshotAfter(s, string.format("%02d-t%.1f", i, s), "expects: turret turning left toward the west")
	end
	Trigger.AfterDelay(TestHarness.TicksForSeconds(9.5), function() Test.Pass("demo: frames captured") end)
end
