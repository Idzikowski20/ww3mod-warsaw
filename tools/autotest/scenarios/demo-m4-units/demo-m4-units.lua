-- DEMO: M4 glTF unit models under the perspective camera.
-- 01: T-90 meshes at four headings (hull yaw), player colours on skirts and turret roof.
-- 02: turrets tracking the Abrams while the duel runs.
-- 03: after the duel, the loser's wreck (t90-wreck.glb if the T-90 died).

WorldLoaded = function()
	TestHarness.FocusBetween(UnitA, UnitB, Show1, Show2)
	Camera.SetView(30, 60)
	TestHarness.ScreenshotAfter(1, "01-headings", "expects: four 3D T-90s, each facing a different way, outlined")

	Trigger.AfterDelay(TestHarness.TicksForSeconds(2), function()
		UnitB.Attack(UnitA, true, true)
		Show1.Attack(UnitA, true, true)
		Show2.Attack(UnitA, true, true)
		UnitA.Attack(UnitB, true, true)
	end)

	TestHarness.ScreenshotAfter(4, "02-turrets", "expects: T-90 turrets turned toward the Abrams")
	Trigger.AfterDelay(TestHarness.TicksForSeconds(19), function() Camera.SetView(200, 70) end)
	TestHarness.ScreenshotAfter(20, "03-aftermath", "expects: wreck model where a T-90 died")
	Trigger.AfterDelay(TestHarness.TicksForSeconds(22), function()
		Test.Pass("demo: frames captured")
	end)
end
