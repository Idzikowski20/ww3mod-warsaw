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
using System.IO;
using OpenRA.FileFormats;
using OpenRA.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.Common.Graphics
{
	/// <summary>
	/// The perspective camera's unit marker, drawn in view px over the model: a shield (pentagon pointing
	/// down) in the colour of the viewer's relationship to the owner, holding the unit's silhouette.
	/// Selected: filled with that colour and the silhouette turns white; under the mouse: a brighter rim.
	/// Under the shield, a health bar in the same colour, always shown (the user's call, 2026-10-28: WW3MOD
	/// had shipped without one since 2024, health read from the damage pip; under the perspective camera
	/// the marker carries it, as in Broken Arrow).
	/// </summary>
	public class UnitMarkerRenderable : IRenderable, IFinalizedRenderable
	{
		static readonly Color Own = Color.FromArgb(70, 200, 110);
		static readonly Color Ally = Color.FromArgb(70, 150, 235);
		static readonly Color Enemy = Color.FromArgb(225, 60, 55);
		static readonly Color Neutral = Color.FromArgb(170, 170, 160);

		readonly Actor actor;
		readonly Rectangle bounds;
		readonly Color color;
		readonly Sprite icon;
		readonly bool selected, rollover;

		public UnitMarkerRenderable(Actor actor, Rectangle bounds, Color color, Sprite icon, bool selected, bool rollover)
		{
			this.actor = actor;
			this.bounds = bounds;
			this.color = color;
			this.icon = icon;
			this.selected = selected;
			this.rollover = rollover;
		}

		/// <summary>Green for the viewer's own units, blue allies, red enemies, grey otherwise.</summary>
		public static Color RelationColor(Actor self, WorldRenderer wr)
		{
			var viewer = wr.World.RenderPlayer;
			if (viewer == null)
				return self.OwnerColor();

			if (self.Owner == viewer)
				return Own;

			return self.Owner.RelationshipWith(viewer) switch
			{
				PlayerRelationship.Ally => Ally,
				PlayerRelationship.Enemy => Enemy,
				_ => Neutral
			};
		}

		public WPos Pos => actor.CenterPosition;
		public int ZOffset => 0;
		public bool IsDecoration => true;

		public IRenderable WithZOffset(int newOffset) { return this; }
		public IRenderable OffsetBy(in WVec vec) { return this; }
		public IRenderable AsDecoration() { return this; }
		public IFinalizedRenderable PrepareRender(WorldRenderer wr) { return this; }

		public void Render(WorldRenderer wr)
		{
			if (!actor.IsInWorld || actor.IsDead)
				return;

			float l = bounds.Left, r = bounds.Right, t = bounds.Top, b = bounds.Bottom;
			var shoulder = t + bounds.Height * 0.62f;
			var tl = new float3(l, t, 0);
			var tr = new float3(r, t, 0);
			var mr = new float3(r, shoulder, 0);
			var ml = new float3(l, shoulder, 0);
			var tip = new float3((l + r) / 2, b, 0);

			var fill = selected ? Color.FromArgb(170, color) : Color.FromArgb(120, 16, 20, 18);
			var cr = Game.Renderer.RgbaColorRenderer;
			cr.FillRect(tl, tr, mr, ml, fill);
			cr.FillRect(ml, mr, tip, tip, fill);
			var rim = selected || rollover ? Color.FromArgb(255, Math.Min(255, color.R + 60), Math.Min(255, color.G + 60), Math.Min(255, color.B + 60)) : color;
			cr.DrawPolygon(new[] { tl, tr, mr, tip, ml }, selected ? 2 : 1, rim);

			var health = actor.TraitOrDefault<IHealth>();
			if (health != null && health.MaxHP > 0)
				DrawHealthBar(cr, l, r, b + HealthBarGap, (float)health.HP / health.MaxHP);

			if (icon == null)
				return;

			// The silhouette fits the shield's upper box with a small inset, keeping its proportions.
			var boxW = bounds.Width - 6f;
			var boxH = shoulder - t + (b - shoulder) * 0.35f - 4f;
			var scale = Math.Min(boxW / icon.Size.X, boxH / icon.Size.Y);
			var size = new float2(icon.Size.X * scale, icon.Size.Y * scale);
			var at = new float3((l + r - size.X) / 2, t + 3 + (boxH - size.Y) / 2, 0);
			var tint = selected ? new float3(1, 1, 1) : new float3(color.R / 255f, color.G / 255f, color.B / 255f);
			Game.Renderer.RgbaSpriteRenderer.DrawSprite(icon, at, scale, tint, 1f);
		}

		/// <summary>View px below the marker's bounds that its health bar and anything hung under it take.</summary>
		public const int HealthBarGap = 3;
		public const int HealthBarHeight = 4;

		void DrawHealthBar(RgbaColorRenderer cr, float l, float r, float y, float fraction)
		{
			var back = Color.FromArgb(170, 12, 14, 12);
			cr.FillRect(new float3(l, y, 0), new float3(r, y + HealthBarHeight, 0), back);
			var fill = Math.Clamp(fraction, 0f, 1f) * (r - l - 2);
			if (fill > 0)
				cr.FillRect(new float3(l + 1, y + 1, 0), new float3(l + 1 + fill, y + HealthBarHeight - 1, 0), color);

			// Quarter ticks, as the reference bar has.
			for (var i = 1; i < 4; i++)
			{
				var x = l + 1 + (r - l - 2) * i / 4f;
				cr.DrawLine(new float3(x, y + 1, 0), new float3(x, y + HealthBarHeight - 1, 0), 1, back);
			}
		}

		public void RenderDebugGeometry(WorldRenderer wr) { }
		public Rectangle ScreenBounds(WorldRenderer wr) { return Rectangle.Empty; }
	}

	/// <summary>
	/// Unit silhouettes for markers: a white-on-transparent PNG beside each model, &lt;model&gt;-icon.png
	/// (tools/models/silhouettes.py renders them from the .glb files).
	/// </summary>
	public static class MarkerIcons
	{
		// ponytail: one process-wide sheet, never freed; a few dozen 128x48 icons. Move it onto ModData if
		// mods ever hot-swap.
		static readonly Dictionary<string, Sprite> Cache = new();
		static SheetBuilder sheet;

		public static Sprite Get(string model)
		{
			if (model == null)
				return null;

			if (Cache.TryGetValue(model, out var sprite))
				return sprite;

			var file = Path.ChangeExtension(model, null) + "-icon.png";
			if (Game.ModData.DefaultFileSystem.TryOpen(file, out var s))
			{
				using (s)
				{
					sheet ??= new SheetBuilder(SheetType.BGRA, 1024);
					sprite = sheet.Add(new Png(s));
				}
			}

			return Cache[model] = sprite;
		}
	}
}
