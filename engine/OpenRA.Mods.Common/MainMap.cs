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

namespace OpenRA.Mods.Common
{
	/// <summary>mod.yaml `MainMap: Map: <folder or title>`: the map a new skirmish starts on.</summary>
	public class MainMap : IGlobalModData
	{
		[Desc("Map package folder name or title. Empty = the engine's own pick (last played or random).")]
		public readonly string Map = null;
	}
}
