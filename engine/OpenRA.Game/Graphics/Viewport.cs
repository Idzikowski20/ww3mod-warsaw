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
using System.Collections.Generic;
using System.Linq;
using OpenRA.Primitives;

namespace OpenRA.Graphics
{
	[Flags]
	public enum ScrollDirection { None = 0, Up = 1, Left = 2, Down = 4, Right = 8 }

	public interface INotifyViewportZoomExtentsChanged
	{
		void ViewportZoomExtentsChanged(float minZoom, float maxZoom);
	}

	public static class ViewportExts
	{
		public static bool Includes(this ScrollDirection d, ScrollDirection s)
		{
			// PERF: Enum.HasFlag is slower and requires allocations.
			return (d & s) == s;
		}

		public static ScrollDirection Set(this ScrollDirection d, ScrollDirection s, bool val)
		{
			return (d.Includes(s) != val) ? d ^ s : d;
		}
	}

	public class Viewport
	{
		readonly WorldRenderer worldRenderer;
		readonly WorldViewportSizes viewportSizes;
		readonly GraphicSettings graphicSettings;

		// Map bounds (world-px)
		readonly Rectangle mapBounds;
		readonly Size tileSize;

		// Perspective camera (mod.yaml PerspectiveCamera.Enabled). Null = the classic 2D viewport.
		// With it the world is a plane under the camera: TopLeft/BottomRight bound the ground it sees.
		readonly Camera3D camera;
		Rectangle visibleGround;

		// Map sprites stand north of their cell in world px (tall art, aircraft at altitude), so the
		// culling box is grown by this many cells past the ground the camera sees.
		const int VisibleGroundMarginCells = 8;

		public Camera3D Camera => camera;
		public bool Is3D => camera != null;

		// Viewport geometry (world-px)
		public int2 CenterLocation { get; private set; }

		public WPos CenterPosition => worldRenderer.ProjectedPosition(CenterLocation);

		public Rectangle Rectangle => new(camera != null ? int2.Zero : TopLeft, new Size(viewportSize.X, viewportSize.Y));
		public int2 TopLeft => camera != null ? visibleGround.Location : CenterLocation - viewportSize / 2;
		public int2 BottomRight => camera != null ? visibleGround.BottomRight : CenterLocation + viewportSize / 2;
		int2 viewportSize;
		ProjectedCellRegion cells;
		bool cellsDirty = true;

		ProjectedCellRegion allCells;
		bool allCellsDirty = true;

		WorldViewport lastViewportDistance;

		float zoom = 1f;
		bool unlockMinZoom = true;
		float unlockedMinZoomScale = 0.25f;
		float unlockedMinZoom = 0.25f;

		public float Zoom
		{
			get => zoom;

			private set
			{
				zoom = value;
				viewportSize = (1f / zoom * new float2(Game.Renderer.NativeResolution)).ToInt2();
				cellsDirty = true;
				allCellsDirty = true;
			}
		}

		public float MinZoom { get; private set; } = 1f;
		public float MaxZoom { get; private set; } = 4f;

		/// <summary>
		/// The lowest zoom the viewport will actually accept, which is NOT <see cref="MinZoom"/>.
		/// WW3MOD leaves <c>unlockMinZoom</c> on for everyone (field initialiser above, and nothing
		/// in the tree ever clears it), so the real floor in normal play is MinZoom * 0.25 — the
		/// same place the mouse wheel already stops. <see cref="UpdateViewportZooms"/> sizes the
		/// renderer's maximum viewport to exactly this, so it is also the point past which a
		/// zoom-out would ask for a sheet larger than the one allocated for it.
		/// </summary>
		public float EffectiveMinZoom => unlockMinZoom ? unlockedMinZoom : MinZoom;

		/// <summary>Set zoom directly, clamped to the same range <see cref="AdjustZoom(float)"/> uses.</summary>
		public void SetZoom(float value)
		{
			Zoom = value.Clamp(EffectiveMinZoom, MaxZoom);
		}

		public void AdjustZoom(float dz)
		{
			// Zooming in (dz > 0) is one wheel notch down for the perspective camera.
			if (camera != null)
			{
				if (dz != 0)
					camera.Scroll(-Math.Sign(dz));
				return;
			}

			// Exponential ensures that equal positive and negative steps have the same effect
			SetZoom(zoom * (float)Math.Exp(dz));
		}

		public void AdjustZoom(float dz, int2 center)
		{
			if (camera != null)
			{
				AdjustZoom(dz);
				return;
			}

			var oldCenter = worldRenderer.Viewport.ViewToWorldPx(center);
			AdjustZoom(dz);
			var newCenter = worldRenderer.Viewport.ViewToWorldPx(center);
			CenterLocation += oldCenter - newCenter;
		}

		public void ToggleZoom()
		{
			// Unlocked zooms always reset to the default zoom
			if (zoom < MinZoom)
				Zoom = MinZoom;
			else
				Zoom = zoom > MinZoom ? MinZoom : MaxZoom;
		}

		public void UnlockMinimumZoom(float scale)
		{
			unlockMinZoom = true;
			unlockedMinZoomScale = scale;
			UpdateViewportZooms(false);
		}

		public static long LastMoveRunTime = 0;
		public static int2 LastMousePos;

		public ScrollDirection GetBlockedDirections()
		{
			var ret = ScrollDirection.None;
			if (camera != null)
				return ret;

			if (CenterLocation.Y <= mapBounds.Top)
				ret |= ScrollDirection.Up;
			if (CenterLocation.X <= mapBounds.Left)
				ret |= ScrollDirection.Left;
			if (CenterLocation.Y >= mapBounds.Bottom)
				ret |= ScrollDirection.Down;
			if (CenterLocation.X >= mapBounds.Right)
				ret |= ScrollDirection.Right;

			return ret;
		}

		public Viewport(WorldRenderer wr, Map map)
		{
			worldRenderer = wr;
			var grid = Game.ModData.Manifest.Get<MapGrid>();
			viewportSizes = Game.ModData.Manifest.Get<WorldViewportSizes>();
			graphicSettings = Game.Settings.Graphics;

			// Calculate map bounds in world-px
			if (wr.World.Type == WorldType.Editor)
			{
				// The full map is visible in the editor
				var width = map.MapSize.X * grid.TileSize.Width;
				var height = map.MapSize.Y * grid.TileSize.Height;
				if (wr.World.Map.Grid.Type == MapGridType.RectangularIsometric)
					height /= 2;

				mapBounds = new Rectangle(0, 0, width, height);
				CenterLocation = new int2(width / 2, height / 2);
			}
			else
			{
				var tl = wr.ScreenPxPosition(map.ProjectedTopLeft);
				var br = wr.ScreenPxPosition(map.ProjectedBottomRight);
				mapBounds = Rectangle.FromLTRB(tl.X, tl.Y, br.X, br.Y);
				CenterLocation = (tl + br) / 2;
			}

			tileSize = grid.TileSize;

			var perspective = Game.ModData.Manifest.Get<PerspectiveCamera>();
			if (perspective.Enabled && wr.World.Type != WorldType.Editor)
			{
				camera = new Camera3D(perspective, tileSize.Height / perspective.MetresPerCell, mapBounds, Game.Renderer.NativeResolution);
				RefreshCamera();
			}

			UpdateViewportZooms();
		}

		/// <summary>
		/// Advances the perspective camera one frame. <paramref name="input"/> is the screen pan direction
		/// (x right, y up); <paramref name="yawInput"/> is -1, 0 or +1.
		/// </summary>
		public void UpdateCamera(float dt, float2 input, bool fast, int yawInput)
		{
			camera.Update(dt, input, fast, yawInput, Game.Renderer.NativeResolution);
			RefreshCamera();
		}

		/// <summary>Middle drag on the perspective camera, in view px: yaw, or with <paramref name="grab"/> drag the map.</summary>
		public void DragCamera(int2 delta, bool grab)
		{
			var native = ViewToNative * delta.ToFloat2();
			if (grab)
				camera.GrabPan(native);
			else
				camera.DragYaw(native.X);

			RefreshCamera();
		}

		/// <summary>Test hook: pose the perspective camera at a yaw (degrees) and settled altitude (metres).</summary>
		public void SetCameraView(float yaw, float altitude)
		{
			if (camera == null)
				return;

			camera.SetView(yaw, altitude);
			RefreshCamera();
		}

		// View px (mouse, UI layout: Renderer.Resolution) to the camera's screen px (Renderer.NativeResolution).
		// Not UIScale: under OS DPI scaling the two differ by the DPI factor too.
		static float ViewToNative => (float)Game.Renderer.NativeResolution.Height / Game.Renderer.Resolution.Height;

		void RefreshCamera()
		{
			CenterLocation = camera.Target.ToInt2();
			visibleGround = camera.VisibleGround(VisibleGroundMarginCells * tileSize.Height);
			cellsDirty = true;
			allCellsDirty = true;
		}

		public void Tick()
		{
			if (lastViewportDistance != graphicSettings.ViewportDistance)
				UpdateViewportZooms();
		}

		static float CalculateMinimumZoom(float minHeight, float maxHeight)
		{
			var h = Game.Renderer.NativeResolution.Height;

			// Check the easy case: the native resolution is within the maximum limit
			// Also catches the case where the user may force a resolution smaller than the minimum window size
			if (h <= maxHeight)
				return 1;

			// Find a clean fraction that brings us within the desired range to reduce aliasing
			var step = 1f;
			while (true)
			{
				var testZoom = 1f;
				while (true)
				{
					var nextZoom = testZoom + step;
					if (h < minHeight * nextZoom)
						break;

					testZoom = nextZoom;
				}

				if (h < maxHeight * testZoom)
					return testZoom;

				step /= 2;
			}
		}

		void UpdateViewportZooms(bool resetCurrentZoom = true)
		{
			lastViewportDistance = graphicSettings.ViewportDistance;

			// The perspective camera renders the world at window resolution; distance is its altitude, not zoom.
			if (camera != null)
			{
				MinZoom = MaxZoom = unlockedMinZoom = 1f;
				Zoom = 1f;
				var sky = camera.SkyColour;
				Game.Renderer.SetWorldClearColor(Color.FromArgb(255, (int)(255 * sky[0]), (int)(255 * sky[1]), (int)(255 * sky[2])));
				// The world image at the window's physical resolution (times RenderScale), not the OS-scaled one:
				// at 150% Windows scaling the world was drawn at 2/3 size and stretched, which looked jagged.
				// The camera still works in NativeResolution px; RenderViewProjection is resolution-free.
				var scale = Game.ModData.Manifest.Get<PerspectiveCamera>().RenderScale;
				var surface = Game.Renderer.SurfaceResolution;
				viewportSize = new int2((int)(surface.Width * scale), (int)(surface.Height * scale));
				Game.Renderer.SetMaximumViewportSize(new Size(viewportSize.X, viewportSize.Y));
				foreach (var t in worldRenderer.World.WorldActor.TraitsImplementing<INotifyViewportZoomExtentsChanged>())
					t.ViewportZoomExtentsChanged(1f, 1f);

				return;
			}

			Game.Renderer.SetWorldClearColor(default);
			var vd = graphicSettings.ViewportDistance;
			if (viewportSizes.AllowNativeZoom && vd == WorldViewport.Native)
				MinZoom = 1;
			else
			{
				var range = viewportSizes.GetSizeRange(vd);
				MinZoom = CalculateMinimumZoom(range.X, range.Y);
			}

			MaxZoom = Math.Min(MinZoom * viewportSizes.MaxZoomScale, Game.Renderer.NativeResolution.Height * 1f / viewportSizes.MaxZoomWindowHeight);

			if (unlockMinZoom)
			{
				// Spectators and the map editor support zooming out by an extra factor of two.
				// TODO: Allow zooming out until the full map is visible
				// We need to improve our viewport scroll handling to center the map as we zoom out
				// before this will work well enough to enable
				unlockedMinZoom = MinZoom * unlockedMinZoomScale;
			}

			if (resetCurrentZoom)
				Zoom = MinZoom;
			else
				Zoom = Zoom.Clamp(MinZoom, MaxZoom);

			var minZoom = EffectiveMinZoom;
			var maxSize = 1f / minZoom * new float2(Game.Renderer.NativeResolution);
			Game.Renderer.SetMaximumViewportSize(new Size((int)maxSize.X, (int)maxSize.Y));

			foreach (var t in worldRenderer.World.WorldActor.TraitsImplementing<INotifyViewportZoomExtentsChanged>())
				t.ViewportZoomExtentsChanged(minZoom, MaxZoom);
		}

		public CPos ViewToWorld(int2 view)
		{
			var world = worldRenderer.Viewport.ViewToWorldPx(view);
			var map = worldRenderer.World.Map;
			var candidates = CandidateMouseoverCells(world).ToList();

			foreach (var uv in candidates)
			{
				// Coarse filter to nearby cells
				var p = map.CenterOfCell(uv.ToCPos(map.Grid.Type));
				var s = worldRenderer.ScreenPxPosition(p);
				if (Math.Abs(s.X - world.X) <= tileSize.Width && Math.Abs(s.Y - world.Y) <= tileSize.Height)
				{
					var ramp = map.Grid.Ramps[map.Ramp.Contains(uv) ? map.Ramp[uv] : 0];
					var pos = map.CenterOfCell(uv.ToCPos(map)) - new WVec(0, 0, ramp.CenterHeightOffset);
					var screen = ramp.Corners.Select(c => worldRenderer.ScreenPxPosition(pos + c)).ToArray();
					if (screen.PolygonContains(world))
						return uv.ToCPos(map);
				}
			}

			// Mouse is not directly over a cell (perhaps on a cliff)
			// Try and find the closest cell
			if (candidates.Count > 0)
			{
				return candidates.MinBy(uv =>
				{
					var p = map.CenterOfCell(uv.ToCPos(map.Grid.Type));
					var s = worldRenderer.ScreenPxPosition(p);
					var dx = Math.Abs(s.X - world.X);
					var dy = Math.Abs(s.Y - world.Y);

					return dx * dx + dy * dy;
				}).ToCPos(map);
			}

			// Something is very wrong, but lets return something that isn't completely bogus and hope the caller can recover
			return worldRenderer.World.Map.CellContaining(worldRenderer.ProjectedPosition(ViewToWorldPx(view)));
		}

		/// <summary>Returns an unfiltered list of all cells that could potentially contain the mouse cursor.</summary>
		IEnumerable<MPos> CandidateMouseoverCells(int2 world)
		{
			var map = worldRenderer.World.Map;
			var tileScale = map.Grid.TileScale / 2;
			var minPos = worldRenderer.ProjectedPosition(world);

			// Find all the cells that could potentially have been clicked.
			MPos a;
			MPos b;
			if (map.Grid.Type == MapGridType.RectangularIsometric)
			{
				// TODO: this generates too many cells.
				a = map.CellContaining(minPos - new WVec(tileScale, 0, 0)).ToMPos(map.Grid.Type);
				b = map.CellContaining(minPos + new WVec(tileScale, tileScale * map.Grid.MaximumTerrainHeight, 0)).ToMPos(map.Grid.Type);
			}
			else
			{
				a = map.CellContaining(minPos).ToMPos(map.Grid.Type);
				b = map.CellContaining(minPos + new WVec(0, tileScale * map.Grid.MaximumTerrainHeight, 0)).ToMPos(map.Grid.Type);
			}

			for (var v = b.V; v >= a.V; v--)
				for (var u = b.U; u >= a.U; u--)
					yield return new MPos(u, v);
		}

		// With the perspective camera the world px plane is the ground: view px go through it by ray, and any
		// float3 is placed at its XY (the 2D world is drawn flat, so its Z depth is not a height).
		public int2 ViewToWorldPx(int2 view)
		{
			if (camera != null)
				return camera.GroundAt(ViewToNative * view.ToFloat2()).ToInt2();

			return (graphicSettings.UIScale / Zoom * view.ToFloat2()).ToInt2() + TopLeft;
		}

		/// <summary>Perspective camera only: view px of a point above the ground (world px x and z, height y up).</summary>
		public int2 WorldToViewPx3D(in float3 xyz)
		{
			return (camera.ProjectPoint(xyz) / ViewToNative).ToInt2();
		}

		public int2 WorldToViewPx(int2 world)
		{
			if (camera != null)
				return (camera.Project(world) / ViewToNative).ToInt2();

			return (Zoom / graphicSettings.UIScale * (world - TopLeft).ToFloat2()).ToInt2();
		}

		public int2 WorldToViewPx(in float3 world)
		{
			if (camera != null)
				return (camera.Project(world.XY) / ViewToNative).ToInt2();

			return (Zoom / graphicSettings.UIScale * (world - TopLeft).XY).ToInt2();
		}

		// Sub-pixel counterpart of WorldToViewPx. That overload truncates to whole pixels (float2.ToInt2 is
		// (int)X, (int)Y), which is right for placing a sprite or a selection box and wrong for a tessellated
		// curve: every vertex snaps independently, so each one lands up to a pixel off the curve in each axis,
		// short segments lose a large fraction of their length, and short enough ones collapse onto a single
		// pixel — at which point RgbaColorRenderer.DrawLine divides by a zero length and emits NaN vertices
		// that draw nothing at all. The snap pattern is also a function of TopLeft and Zoom rather than of the
		// world, so it re-rolls as the viewport scrolls or the subject moves. Curves want this instead.
		public static float2 ProjectToViewPx(in float3 world, int2 topLeft, float scale) { return scale * (world - topLeft).XY; }
		public float ViewPxScale => camera != null ? camera.PxScaleAtTarget / ViewToNative : Zoom / graphicSettings.UIScale;

		public float2 WorldToViewPxF(in float3 world)
		{
			if (camera != null)
				return camera.Project(world.XY) / ViewToNative;

			return ProjectToViewPx(world, TopLeft, ViewPxScale);
		}

		public void Center(IEnumerable<Actor> actors)
		{
			var actorsCollection = actors as IReadOnlyCollection<Actor>;
			actorsCollection ??= actors.ToList();

			if (actorsCollection.Count == 0)
				return;

			Center(actorsCollection.Select(a => a.CenterPosition).Average());
		}

		public void Center(WPos pos)
		{
			if (camera != null)
			{
				camera.CenterOn(worldRenderer.ScreenPxPosition(pos));
				RefreshCamera();
				return;
			}

			CenterLocation = worldRenderer.ScreenPxPosition(pos).Clamp(mapBounds);
			cellsDirty = true;
			allCellsDirty = true;
		}

		/// <summary>
		/// Offsets the viewport centre by an EXACT integer amount, with no zoom conversion and no
		/// truncation. Scroll() rounds `1/Zoom * delta` toward zero, which is fine for input-driven
		/// scrolling but loses a fraction of a pixel every call — over a shake that applies a delta
		/// every tick, those losses accumulate into a camera that never returns to where it started.
		/// ScreenShaker drives an absolute offset through this instead, so its displacement is
		/// exactly reversible. Deliberately ignores map borders: the caller is responsible for
		/// putting back whatever it applied.
		/// </summary>
		public void ScrollPx(int2 delta)
		{
			if (camera != null)
			{
				camera.Offset(delta);
				RefreshCamera();
				return;
			}

			CenterLocation += delta;
			cellsDirty = true;
			allCellsDirty = true;
		}

		public void Scroll(float2 delta, bool ignoreBorders)
		{
			if (camera != null)
			{
				camera.PanScreen(delta);
				RefreshCamera();
				return;
			}

			// Convert scroll delta from world-px to viewport-px
			CenterLocation += (1f / Zoom * delta).ToInt2();
			cellsDirty = true;
			allCellsDirty = true;

			if (!ignoreBorders)
				CenterLocation = CenterLocation.Clamp(mapBounds);
		}

		// Rectangle (in viewport coords) that contains things to be drawn
		public Rectangle GetScissorBounds(bool insideBounds)
		{
			// Under perspective the map edge is not a screen rectangle: draw the whole window.
			if (camera != null)
				return new Rectangle(0, 0, viewportSize.X, viewportSize.Y);

			// Visible rectangle in world coordinates (expanded to the corners of the cells)
			var bounds = insideBounds ? VisibleCellsInsideBounds : AllVisibleCells;
			var map = worldRenderer.World.Map;
			var ctl = map.CenterOfCell(((MPos)bounds.TopLeft).ToCPos(map)) - new WVec(512, 512, 0);
			var cbr = map.CenterOfCell(((MPos)bounds.BottomRight).ToCPos(map)) + new WVec(512, 512, 0);

			// Convert to screen coordinates
			var tl = worldRenderer.ScreenPxPosition(ctl - new WVec(0, 0, ctl.Z)) - TopLeft;
			var br = worldRenderer.ScreenPxPosition(cbr - new WVec(0, 0, cbr.Z)) - TopLeft;

			// Add an extra half-cell fudge to avoid clipping isometric tiles
			return Rectangle.FromLTRB(tl.X - tileSize.Width / 2, tl.Y - tileSize.Height / 2,
				br.X + tileSize.Width / 2, br.Y + tileSize.Height / 2);
		}

		ProjectedCellRegion CalculateVisibleCells(bool insideBounds)
		{
			var map = worldRenderer.World.Map;

			// Calculate the projected cell position at the corners of the visible area
			var tl = (PPos)map.CellContaining(worldRenderer.ProjectedPosition(TopLeft)).ToMPos(map);
			var br = (PPos)map.CellContaining(worldRenderer.ProjectedPosition(BottomRight)).ToMPos(map);

			// RectangularIsometric maps don't have straight edges, and so we need an additional
			// cell margin to include the cells that are half visible on each edge.
			if (map.Grid.Type == MapGridType.RectangularIsometric)
			{
				tl = new PPos(tl.U - 1, tl.V - 1);
				br = new PPos(br.U + 1, br.V + 1);
			}

			// Clamp to the visible map bounds, if requested
			if (insideBounds)
			{
				tl = map.Clamp(tl);
				br = map.Clamp(br);
			}

			return new ProjectedCellRegion(map, tl, br);
		}

		public ProjectedCellRegion VisibleCellsInsideBounds
		{
			get
			{
				if (cellsDirty)
				{
					cells = CalculateVisibleCells(true);
					cellsDirty = false;
				}

				return cells;
			}
		}

		public ProjectedCellRegion AllVisibleCells
		{
			get
			{
				if (allCellsDirty)
				{
					allCells = CalculateVisibleCells(false);
					allCellsDirty = false;
				}

				return allCells;
			}
		}
	}
}
