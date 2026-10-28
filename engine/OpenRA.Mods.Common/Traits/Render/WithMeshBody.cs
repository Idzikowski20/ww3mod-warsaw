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

		[Desc("Length of one tile of the track texture (material \"track*\"), model metres. 0.7: two links of a T-72-class track.")]
		public readonly float TrackTileLength = 0.7f;

		public override object Create(ActorInitializer init) { return new WithMeshBody(init.Self, this); }
	}

	public class WithMeshBody : ConditionalTrait<WithMeshBodyInfo>, IRender, IAutoMouseBounds, INotifyAttack, ITick
	{
		readonly GltfModel mesh;
		IFacing facing;
		IMove move;
		(int Node, Turreted Turret)[] turrets = Array.Empty<(int, Turreted)>();
		float clipTime, attackTime = -1f;

		// The last two ticks' pose, drawn interpolated by SubTickClock: the world ticks 16.67 times a second
		// and a model stepping between ticks visibly judders (turrets most). View state only, never synced.
		WPos lastPos, pos;
		float lastBodyYaw, bodyYaw;
		float[] lastTurretYaw = Array.Empty<float>(), turretYaw = Array.Empty<float>();
		bool posed;

		// Distance driven, in track tiles (signed: reversing runs it back), for the "track" parts' texture scroll.
		// View state only, never synced; kept small by dropping whole tiles from both values.
		float lastTrack, track;

		// Where the last frame drew the model, for the unit marker. View state written only by Render.
		WPos drawnPosition;

		public WithMeshBody(Actor self, WithMeshBodyInfo info)
			: base(info)
		{
			mesh = GltfModel.Get(info.Model);
		}

		// Bound here, not in the constructor: traits are constructed in dependency order and this one does not
		// require Turreted or the mover, so they may not exist yet when it is built (the turrets never turned).
		protected override void Created(Actor self)
		{
			facing = self.TraitOrDefault<IFacing>();
			move = self.TraitOrDefault<IMove>();
			var all = self.TraitsImplementing<Turreted>().ToArray();
			turrets = Info.TurretNodes
				.Select(kv => (mesh.NodeIndex(kv.Key), all.FirstOrDefault(t => t.Name == kv.Value)))
				.Where(t => t.Item1 >= 0 && t.Item2 != null)
				.ToArray();
			// The sprite turret quantised the turret to its sprite's facings, which makes shells and muzzle flashes
			// jump between 32 directions while the model's barrel turns smoothly.
			foreach (var t in turrets)
				t.Turret.QuantizedFacings = 0;

			lastTurretYaw = new float[turrets.Length];
			turretYaw = new float[turrets.Length];
			base.Created(self);
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

			lastPos = pos;
			lastBodyYaw = bodyYaw;
			Array.Copy(turretYaw, lastTurretYaw, turretYaw.Length);
			ReadPose(self);
			if (!posed)
			{
				lastPos = pos;
				lastBodyYaw = bodyYaw;
				Array.Copy(turretYaw, lastTurretYaw, turretYaw.Length);
				posed = true;
			}

			// ponytail: both belts scroll by the hull's travel, so a pivot turn on the spot leaves them still
			// (real tracks counter-rotate). Upgrade: per-belt scroll = travel +- yaw change x half the track gauge,
			// with a TrackScroll per side (left/right track materials).
			var moved = pos - lastPos;
			var forward = new WVec(0, -1024, 0).Rotate(WRot.FromYaw(facing != null ? facing.Facing : WAngle.Zero));
			var metres = moved.HorizontalLength * Game.ModData.Manifest.Get<PerspectiveCamera>().MetresPerCell / 1024f / Info.Scale;
			var whole = MathF.Floor(track);
			lastTrack = track - whole;
			track = lastTrack + MathF.Sign(moved.X * forward.X + moved.Y * forward.Y) * metres / Info.TrackTileLength;
		}

		void ReadPose(Actor self)
		{
			pos = self.CenterPosition;
			bodyYaw = facing != null ? Yaw(facing.Facing) : 0f;
			for (var i = 0; i < turrets.Length; i++)
				turretYaw[i] = Yaw(turrets[i].Turret.LocalOrientation.Yaw);
		}

		static float LerpAngle(float a, float b, float t)
		{
			var d = (b - a) % (2 * MathF.PI);
			if (d > MathF.PI)
				d -= 2 * MathF.PI;
			else if (d < -MathF.PI)
				d += 2 * MathF.PI;

			return a + d * t;
		}

		/// <summary>Where the model was last drawn (between the last two ticks); the unit marker follows it.</summary>
		public WPos RenderPosition(Actor self)
		{
			return posed ? drawnPosition : self.CenterPosition;
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

			if (!posed)
			{
				ReadPose(self);
				lastPos = pos;
				lastBodyYaw = bodyYaw;
				Array.Copy(turretYaw, lastTurretYaw, turretYaw.Length);
				posed = true;
			}

			// How far between the last two ticks to draw; a paused world holds the latest pose. SubTickClock is
			// read here, in the render entry point, and only reaches this frame's renderable and drawnPosition
			// (view state, never synced) - SubTickClockIsNotSimulationStateTest.
			var t = self.World.SimulationIsAdvancing ? SubTickClock.Fraction / (float)SubTickClock.One : 1f;
			drawnPosition = lastPos + (pos - lastPos) * (int)(t * 1024) / 1024;
			var drawYaw = LerpAngle(lastBodyYaw, bodyYaw, t);
			Dictionary<int, float> extraYaw = null;
			if (turrets.Length > 0)
			{
				extraYaw = new Dictionary<int, float>();
				for (var i = 0; i < turrets.Length; i++)
					extraYaw[turrets[i].Node] = LerpAngle(lastTurretYaw[i], turretYaw[i], t);
			}

			var clip = CurrentClip(out var time);
			var nodes = mesh.WorldMatrices(clip, time, extraYaw);

			// Metres to world px: the camera's scale; world px y is south, the 3D frame's z.
			var at = drawnPosition;
			var px = (float)wr.TileSize.Height / wr.TileScale;
			var metres = Info.Scale * wr.TileSize.Height / Game.ModData.Manifest.Get<PerspectiveCamera>().MetresPerCell;
			var model = Matrix4x4.CreateScale(metres) * Matrix4x4.CreateRotationY(drawYaw)
				* Matrix4x4.CreateTranslation(at.X * px, at.Z * px, at.Y * px);

			var scroll = lastTrack + (track - lastTrack) * t;
			return new IRenderable[] { new GltfRenderable(mesh, at, model, nodes, self.OwnerColor(), scroll) };
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
