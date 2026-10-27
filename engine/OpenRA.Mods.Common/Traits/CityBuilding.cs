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
using OpenRA.Traits;

namespace OpenRA.Mods.Common.Traits
{
	/// <summary>Index of the CityMap mesh an actor stands for (map.yaml `CityBuilding: 42`).</summary>
	public class CityBuildingInit : ValueActorInit<int>, ISingleInstanceInit
	{
		public CityBuildingInit(int value)
			: base(value) { }
	}

	[Desc("One building of the world's CityMap: blocks every cell its mesh stands on (an irregular, per-instance",
		"footprint that the fixed Building footprint cannot express), exposes them for HitShape, and hides the mesh when removed.")]
	public class CityBuildingInfo : TraitInfo, IOccupySpaceInfo
	{
		public override object Create(ActorInitializer init) { return new CityBuilding(init); }

		// Per-type answer for placement previews and the editor: the real footprint is only known per instance.
		public IReadOnlyDictionary<CPos, SubCell> OccupiedCells(ActorInfo info, CPos location, SubCell subCell = SubCell.Any)
		{
			return new Dictionary<CPos, SubCell>() { { location, SubCell.FullCell } };
		}

		bool IOccupySpaceInfo.SharesCell => false;
	}

	public class CityBuilding : IOccupySpace, ITargetableCells, ISync, INotifyAddedToWorld, INotifyRemovedFromWorld
	{
		readonly CityMap city;
		readonly int index;
		readonly (CPos, SubCell)[] occupied;

		public CityBuilding(ActorInitializer init)
		{
			city = init.World.WorldActor.Trait<CityMap>();
			index = init.GetValue<CityBuildingInit, int>();
			TopLeft = init.GetValue<LocationInit, CPos>();

			var cells = city.Footprint(index);
			if (cells.Count == 0)
				cells = new[] { TopLeft };

			occupied = cells.Select(c => (c, SubCell.FullCell)).ToArray();

			var map = init.World.Map;
			var sum = WVec.Zero;
			foreach (var c in cells)
				sum += map.CenterOfCell(c) - WPos.Zero;

			CenterPosition = WPos.Zero + sum / cells.Count;
		}

		[Sync]
		public CPos TopLeft { get; }

		[Sync]
		public WPos CenterPosition { get; }

		public (CPos, SubCell)[] OccupiedCells() { return occupied; }

		(CPos Cell, SubCell SubCell)[] ITargetableCells.TargetableCells() { return occupied; }

		void INotifyAddedToWorld.AddedToWorld(Actor self)
		{
			self.World.AddToMaps(self, this);
			city.SetVisible(index, true);
		}

		void INotifyRemovedFromWorld.RemovedFromWorld(Actor self)
		{
			self.World.RemoveFromMaps(self, this);
			city.SetVisible(index, false);
		}
	}
}
