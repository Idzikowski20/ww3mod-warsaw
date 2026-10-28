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

using System.Collections.Generic;
using System.Linq;
using OpenRA.Graphics;
using OpenRA.Mods.Common.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.Common.Traits.Render
{
	public class SelectionDecorationsInfo : SelectionDecorationsBaseInfo, Requires<InteractableInfo>
	{
		public override object Create(ActorInitializer init) { return new SelectionDecorations(init.Self, this); }
	}

	public class SelectionDecorations : SelectionDecorationsBase, IRender
	{
		readonly Interactable interactable;

		public SelectionDecorations(Actor self, SelectionDecorationsInfo info)
			: base(info)
		{
			interactable = self.Trait<Interactable>();
		}

		// Perspective camera: a Broken Arrow style marker floats over the model's top, and every decoration,
		// bar and highlight is laid out on it in view px. The flat world-px bounds would sit on the ground
		// north of a 3D model, which is what made the pips drift off the units.
		const int MarkerWidth = 38;
		const int MarkerHeight = 34;
		const int MarkerGap = 6;
		const float DefaultTopMetres = 4f;
		WithMeshBody[] meshes;

		WithMeshBody Mesh(Actor self)
		{
			meshes ??= self.TraitsImplementing<WithMeshBody>().ToArray();
			return meshes.FirstOrDefault(m => !m.IsTraitDisabled);
		}

		/// <summary>The marker rectangle in view px.</summary>
		public Rectangle MarkerBounds(Actor self, WorldRenderer wr)
		{
			var pos = self.CenterPosition;
			var px = (float)wr.TileSize.Height / wr.TileScale;
			var top = Mesh(self)?.TopPx(wr)
				?? DefaultTopMetres * wr.TileSize.Height / Game.ModData.Manifest.Get<PerspectiveCamera>().MetresPerCell;
			var a = wr.Viewport.WorldToViewPx3D(new float3(pos.X * px, pos.Z * px + top, pos.Y * px));
			return new Rectangle(a.X - MarkerWidth / 2, a.Y - MarkerGap - MarkerHeight, MarkerWidth, MarkerHeight);
		}

		int2 GetDecorationPosition(Actor self, WorldRenderer wr, string pos)
		{
			var bounds = wr.Viewport.Is3D ? MarkerBounds(self, wr) : interactable.DecorationBounds(self, wr);
			switch (pos)
			{
				case "TopLeft": return bounds.TopLeft;
				case "TopRight": return bounds.TopRight;
				case "BottomLeft": return bounds.BottomLeft;
				case "BottomRight": return bounds.BottomRight;
				case "Top": return new int2(bounds.Left + bounds.Size.Width / 2, bounds.Top);
				case "Bottom": return new int2(bounds.Left + bounds.Size.Width / 2, bounds.Bottom);
				default: return bounds.TopLeft + new int2(bounds.Size.Width / 2, bounds.Size.Height / 2);
			}
		}

		// Public so the sign convention can be asserted: for Top and TopRight the X is NEGATED, which
		// reads backwards at every call site in YAML and is what put the visibility diamond 8px right
		// of centre. See DecorationRowGeometry for the rest of the model.
		public static int2 GetDecorationMargin(string pos, int2 margin)
		{
			switch (pos)
			{
				case "TopLeft": return margin;
				case "TopRight": return new int2(-margin.X, margin.Y);
				case "BottomLeft": return new int2(margin.X, -margin.Y);
				case "BottomRight": return -margin;
				case "Top": return new int2(-margin.X, margin.Y);
				case "Bottom": return -margin;
				default: return int2.Zero;
			}
		}

		protected override int2 GetDecorationOrigin(Actor self, WorldRenderer wr, string pos, int2 margin)
		{
			var origin = GetDecorationPosition(self, wr, pos);
			return (wr.Viewport.Is3D ? origin : wr.Viewport.WorldToViewPx(origin)) + GetDecorationMargin(pos, margin);
		}

		protected override IEnumerable<IRenderable> RenderMarker(Actor self, WorldRenderer wr, bool selected, bool rollover)
		{
			if (!wr.Viewport.Is3D || interactable is not Selectable)
				yield break;

			yield return new UnitMarkerRenderable(self, MarkerBounds(self, wr), UnitMarkerRenderable.RelationColor(self, wr),
				MarkerIcons.Get(Mesh(self)?.Info.Model), selected, rollover);
		}

		protected override IEnumerable<IRenderable> RenderSelectionBox(Actor self, WorldRenderer wr, Color color)
		{
			// The marker shows selection under the perspective camera.
			if (wr.Viewport.Is3D)
				yield break;

			var bounds = interactable.DecorationBounds(self, wr);
			yield return new SelectionBoxAnnotationRenderable(self, bounds, color);
		}

		protected override IEnumerable<IRenderable> RenderSelectionBars(Actor self, WorldRenderer wr, bool displayHealth, bool displayExtra)
		{
			// Don't render the selection bars for non-selectable actors
			if (interactable is not Selectable || (!displayHealth && !displayExtra))
				yield break;

			if (wr.Viewport.Is3D)
			{
				var m = MarkerBounds(self, wr);
				yield return new SelectionBarsAnnotationRenderable(self, new Rectangle(m.Left, m.Top, m.Width, m.Height + 3),
					displayHealth, displayExtra, viewSpace: true);
				yield break;
			}

			var bounds = interactable.DecorationBounds(self, wr);
			yield return new SelectionBarsAnnotationRenderable(self, bounds, displayHealth, displayExtra);
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			yield break;
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			yield return interactable.DecorationBounds(self, wr);
		}
	}
}
