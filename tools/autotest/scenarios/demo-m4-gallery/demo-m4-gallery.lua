-- DEMO: the converted models side by side, nobody firing. Frames: Russian vehicles (two rows), aircraft.
WorldLoaded = function()
	for _, a in ipairs(Map.ActorsInWorld) do
		if a.HasProperty("Stance") then a.Stance = "HoldFire" end
	end
	local function shot(t, x, y, yaw, alt, label)
		Trigger.AfterDelay(TestHarness.TicksForSeconds(t), function()
			Camera.Position = WPos.New(x * 1024 + 512, y * 1024 + 512, 0)
			Camera.SetView(yaw, alt)
		end)
		TestHarness.ScreenshotAfter(t + 1.2, label, "expects: 3D models, textured, player colour, marker over each")
	end
	shot(0.5, 20, 10, 20, 110, "01-ru-vehicles")
	shot(2.5, 14, 9, 200, 70, "02-ru-close-a")
	shot(4.5, 28, 13, 200, 70, "03-ru-close-b")
	shot(6.5, 20, 23, 20, 120, "04-aircraft")
	shot(8.5, 15, 23, 210, 75, "05-air-close-a")
	shot(10.5, 27, 26, 210, 75, "06-air-close-b")
	Trigger.AfterDelay(TestHarness.TicksForSeconds(12.5), function() Test.Pass("demo: frames captured") end)
end
