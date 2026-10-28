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
using System.Numerics;
using OpenRA.Graphics;
using OpenRA.Primitives;
using OpenRA.Traits;

namespace OpenRA.Mods.Common.Traits.Render
{
	[Desc("Draws the actor as a 3D glTF model (Graphics/GltfModel.cs) under the perspective camera.",
		"Model space is glTF's: metres, +Y up, the front facing -Z (Blender: front along +Y).",
		"The actor's sprite body and turret stay in the rules and stop drawing (WithSpriteBody, WithSpriteTurret).")]
	public class WithMeshBodyInfo : ConditionalTraitInfo
	{
		[FieldLoader.Require]
		[Desc("The .glb file, a path in the mod file system.")]
		public readonly string Model = null;

		[Desc("Size multiplier over real metres.")]
		public readonly float Scale = 1f;

		[Desc("Nodes turned with the turret of the same name, as NodeName: TurretName.")]
		public readonly Dictionary<string, string> TurretNodes = new();

		[Desc("Animation clips. Moving plays MoveClip; IdleClip otherwise; AttackClip once per shot.")]
		public readonly string IdleClip = "idle";
		public readonly string MoveClip = "move";
		public readonly string AttackClip = "attack";

		public override object Create(ActorInitializer init) { return new WithMeshBody(init.Self, this); }
	}

	public class WithMeshBody : ConditionalTrait<WithMeshBodyInfo>, IRender, IAutoMouseBounds, INotifyAttack, ITick
	{
		readonly GltfModel mesh;
		readonly IFacing facing;
		readonly IMove move;
		readonly (int Node, Turreted Turret)[] turrets;
		float clipTime, attackTime = -1f;

		public WithMeshBody(Actor self, WithMeshBodyInfo info)
			: base(info)
		{
			mesh = GltfModel.Get(info.Model);
			facing = self.TraitOrDefault<IFacing>();
			move = self.TraitOrDefault<IMove>();
			var all = self.TraitsImplementing<Turreted>().ToArray();
			turrets = info.TurretNodes
				.Select(kv => (mesh.NodeIndex(kv.Key), all.FirstOrDefault(t => t.Name == kv.Value)))
				.Where(t => t.Item1 >= 0 && t.Item2 != null)
				.ToArray();
		}

		/// <summary>
		/// For sprite body and turret traits: true while the actor draws as a mesh instead. They stay in the rules
		/// (other traits require them) and simply stop drawing.
		/// </summary>
		public static Func<bool> HidesSprites(Actor self)
		{
			if (!Game.ModData.Manifest.Get<PerspectiveCamera>().Enabled)
				return () => false;

			WithMeshBody[] meshes = null;
			return () => (meshes ??= self.TraitsImplementing<WithMeshBody>().ToArray()).Any(m => !m.IsTraitDisabled);
		}

		/// <summary>Height of the model's top above the actor, world px.</summary>
		public float TopPx(WorldRenderer wr)
		{
			return mesh.BoundsMax.Y * Info.Scale * wr.TileSize.Height / Game.ModData.Manifest.Get<PerspectiveCamera>().MetresPerCell;
		}

		void ITick.Tick(Actor self)
		{
			// The game simulates at its own tick rate; clips are authored in seconds of that time.
			var dt = self.World.Timestep / 1000f;
			clipTime += dt;
			if (attackTime >= 0f)
				attackTime += dt;
		}

		void INotifyAttack.Attacking(Actor self, in Target target, Armament a, Barrel barrel) { attackTime = 0f; }
		void INotifyAttack.PreparingAttack(Actor self, in Target target, Armament a, Barrel barrel) { }

		// OpenRA facing turns counter-clockwise from north; the model's front is -Z (north at yaw 0).
		static float Yaw(WAngle angle)
		{
			var forward = new WVec(0, -1024, 0).Rotate(WRot.FromYaw(angle));
			return MathF.Atan2(-forward.X, -forward.Y);
		}

		GltfModel.Clip CurrentClip(out float time)
		{
			time = clipTime;
			if (attackTime >= 0f && mesh.Clips.TryGetValue(Info.AttackClip, out var attack))
			{
				if (attackTime < attack.Duration)
				{
					time = attackTime;
					return attack;
				}

				attackTime = -1f;
			}

			var moving = move != null && move.CurrentMovementTypes.HasFlag(MovementType.Horizontal);
			return mesh.Clips.GetValueOrDefault(moving ? Info.MoveClip : Info.IdleClip);
		}

		IEnumerable<IRenderable> IRender.Render(Actor self, WorldRenderer wr)
		{
			if (IsTraitDisabled || !wr.Viewport.Is3D)
				return Enumerable.Empty<IRenderable>();

			var bodyYaw = facing != null ? Yaw(facing.Facing) : 0f;
			Dictionary<int, float> extraYaw = null;
			if (turrets.Length > 0)
			{
				extraYaw = new Dictionary<int, float>();
				foreach (var (node, turret) in turrets)
					extraYaw[node] = Yaw(turret.LocalOrientation.Yaw);
			}

			var clip = CurrentClip(out var time);
			var nodes = mesh.WorldMatrices(clip, time, extraYaw);

			// Metres to world px: the camera's scale; world px y is south, the 3D frame's z.
			var pos = self.CenterPosition;
			var px = (float)wr.TileSize.Height / wr.TileScale;
			var metres = Info.Scale * wr.TileSize.Height / Game.ModData.Manifest.Get<PerspectiveCamera>().MetresPerCell;
			var model = Matrix4x4.CreateScale(metres) * Matrix4x4.CreateRotationY(bodyYaw)
				* Matrix4x4.CreateTranslation(pos.X * px, pos.Z * px, pos.Y * px);

			return new IRenderable[] { new GltfRenderable(mesh, pos, model, nodes, self.OwnerColor()) };
		}

		IEnumerable<Rectangle> IRender.ScreenBounds(Actor self, WorldRenderer wr)
		{
			yield return Footprint(self, wr);
		}

		Rectangle IAutoMouseBounds.AutoMouseoverBounds(Actor self, WorldRenderer wr)
		{
			return IsTraitDisabled ? Rectangle.Empty : Footprint(self, wr);
		}

		// Ground-plane square the model covers at any heading, in world px (the plane the camera picks on).
		Rectangle Footprint(Actor self, WorldRenderer wr)
		{
			var extent = Vector2.Max(
				new Vector2(Math.Abs(mesh.BoundsMin.X), Math.Abs(mesh.BoundsMin.Z)),
				new Vector2(Math.Abs(mesh.BoundsMax.X), Math.Abs(mesh.BoundsMax.Z))).Length();
			var r = (int)Math.Ceiling(extent * Info.Scale * wr.TileSize.Height / Game.ModData.Manifest.Get<PerspectiveCamera>().MetresPerCell);
			var c = wr.ScreenPxPosition(self.CenterPosition);
			return new Rectangle(c.X - r, c.Y - r, 2 * r, 2 * r);
		}
	}
}
