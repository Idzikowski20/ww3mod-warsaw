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

using OpenRA.Graphics;
using OpenRA.Traits;

namespace OpenRA.Mods.Common.Traits
{
	[Desc("Anti-aliases the finished world image (FXAA) under the perspective camera: smooths the stair-stepped",
		"edges of 3D models and buildings. Off in the 2D map editor, where it would blur pixel art.")]
	[TraitLocation(SystemActors.World)]
	public class FxaaPostProcessEffectInfo : TraitInfo, ILobbyCustomRulesIgnore
	{
		public override object Create(ActorInitializer init) { return new FxaaPostProcessEffect(init.World); }
	}

	public class FxaaPostProcessEffect : RenderPostProcessPassBase
	{
		readonly bool enabled;

		public FxaaPostProcessEffect(World world)
			: base("fxaa", PostProcessPassType.AfterWorld)
		{
			enabled = world.Type != WorldType.Editor && Game.ModData.Manifest.Get<PerspectiveCamera>().Enabled;
		}

		protected override bool Enabled => enabled;
		protected override void PrepareRender(WorldRenderer wr, IShader shader) { }
	}
}
