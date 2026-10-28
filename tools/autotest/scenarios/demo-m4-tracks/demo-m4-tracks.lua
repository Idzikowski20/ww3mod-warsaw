-- DEMO: a T-90 drives north, seen side-on and close. Its track belts should scroll with the distance driven:
-- the top run moving forward over the hull, the bottom run holding still on the ground.
WorldLoaded = function()
	UnitB.Stance = "HoldFire"
	TestHarness.FocusBetween(UnitB)
	Camera.SetView(90, 50)
	TestHarness.ScreenshotAfter(0.6, "00-parked", "expects: T-90 side-on, belts still")
	Trigger.AfterDelay(TestHarness.TicksForSeconds(0.8), function() UnitB.Move(CPos.New(26, 12)) end)
	for i = 1, 8 do
		local s = 2.0 + (i - 1) * 0.15
		TestHarness.ScreenshotAfter(s, string.format("%02d-t%.2f", i, s), "expects: track links shifted along the belt since the last frame")
	end
	Trigger.AfterDelay(TestHarness.TicksForSeconds(3.6), function() Test.Pass("demo: frames captured") end)
end
