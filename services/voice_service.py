from datetime import datetime, timezone
import os
from models.voice_model import VoiceModel
from models.user_model import UserModel
from utils.time_utils import get_ist_time
from models.attendance_model import AttendanceModel

class VoiceService:
    # State Management (Singleton-like behavior via class attributes)
    # State Management (Singleton-like behavior via class attributes)
    active_sessions = {} # {member_id: session_data}

    # Removed in-memory overtime_users set in favor of DB checks

    @classmethod
    async def start_session(cls, member, channel, silent=False):
        now_ist = get_ist_time()
        is_overtime = False

        # 1. Force Overtime on Weekends
        if now_ist.weekday() >= 5:
            is_overtime = True
        else:
            # 2. Check Database for 'Active' Day Status
            # If user has "dropped" for the day, they are in Overtime.
            today_str = now_ist.strftime('%Y-%m-%d')
            try:
                doc = await AttendanceModel.find_by_date(member.id, channel.guild.id, today_str)
                if doc:
                    commands = doc.get('commands_used', [])
                    # Check if 'drop' or 'auto-drop' command exists
                    has_dropped = any(c.get('command') in ['drop', 'auto-drop'] for c in commands)
                    if has_dropped:
                        is_overtime = True
            except Exception as e:
                print(f"[VoiceService] Error checking attendance for {member.display_name}: {e}")

        # 3. Check for Pre-Work Hours (Before 9 AM)
        # Only if not already overtime (due to weekend/drop)
        overtime_reason = None
        start_hour_str = os.getenv("ATTENDANCE_START_TIME", "09:00")
        try:
            sh, sm = map(int, start_hour_str.split(':'))
            # Create a localized datetime for today's start time
            # Note: now_ist is TZ-aware (IST). We must keep comparisons safe.
            start_threshold = now_ist.replace(hour=sh, minute=sm, second=0, microsecond=0)
            
            if not is_overtime:
                if now_ist < start_threshold:
                    is_overtime = True
                    overtime_reason = "pre_shift"
        except Exception as e:
            print(f"[VoiceService] Error parsing ATTENDANCE_START_TIME: {e}")

        cls.active_sessions[member.id] = {
            'start_time': datetime.now(timezone.utc),
            'channel_id': channel.id,
            'channel_name': channel.name,
            'guild_id': channel.guild.id,
            'user_name': member.display_name,
            'is_overtime': is_overtime,
            'overtime_reason': overtime_reason
        }
        
        if not silent:
            status_msg = " [OVERTIME]" if is_overtime else ""
            print(f"[VoiceService] Session STARTED: {member.display_name} in {channel.name}{status_msg}")

    @classmethod
    async def end_session(cls, member, channel, reason="left", silent=False):
        if member.id in cls.active_sessions:
            session = cls.active_sessions.pop(member.id)
            
            # Times are UTC for duration calc, but we need IST for logic
            start_time_utc = session['start_time']
            end_time_utc = datetime.now(timezone.utc)
            
            # --- Logic for Pre-Shift Split (Overtime -> Regular) ---
            # If session was marked overtime ONLY because it was before 9AM ("pre_shift"),
            # AND it ends AFTER 9AM, we split it.
            
            # We need IST conversion to check the 9AM boundary
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            start_ist = start_time_utc.astimezone(ist)
            end_ist = end_time_utc.astimezone(ist)
            
            triggered_split = False
            
            if session.get('overtime_reason') == 'pre_shift' and reason != 'shift_start':
                start_hour_str = os.getenv("ATTENDANCE_START_TIME", "09:00")
                try:
                    sh, sm = map(int, start_hour_str.split(':'))
                    # 9:00 AM Today
                    split_threshold = end_ist.replace(hour=sh, minute=sm, second=0, microsecond=0)
                    
                    if end_ist > split_threshold and start_ist < split_threshold:
                        triggered_split = True
                        
                        # --- PART 1: Overtime (Start -> 9:00) ---
                        # Calculate duration for part 1
                        # We can subtract timestamps.
                        # Note: split_threshold is IST. Convert to UTC for consistency or just diff.
                        split_threshold_utc = split_threshold.astimezone(timezone.utc)
                        
                        dur_p1 = (split_threshold_utc - start_time_utc).total_seconds()
                        
                        # Log Part 1 (Overtime)
                        await cls._log_single_session(
                             user_id=member.id,
                             guild_id=session['guild_id'],
                             channel_name=session['channel_name'],
                             user_name=session['user_name'],
                             start_time=start_time_utc,
                             end_time=split_threshold_utc,
                             duration=dur_p1,
                             disconnect_reason="split_regular", # Internal markers
                             status="overtime",
                             is_ot=True
                        )
                        
                        # --- PART 2: Regular (9:00 -> End) ---
                        dur_p2 = (end_time_utc - split_threshold_utc).total_seconds()
                        
                        record_p2 = await cls._log_single_session(
                             user_id=member.id,
                             guild_id=session['guild_id'],
                             channel_name=session['channel_name'],
                             user_name=session['user_name'],
                             start_time=split_threshold_utc,
                             end_time=end_time_utc,
                             duration=dur_p2,
                             disconnect_reason=reason,
                             status="regular",
                             is_ot=False
                        )
                        
                        if not silent:
                            print(f"[VoiceService] Session SPLIT for {member.display_name}: {round(dur_p1)}s OT + {round(dur_p2)}s Reg.")
                        
                        return record_p2

                except Exception as e:
                    print(f"[VoiceService] Error during split calculation: {e}")

            # --- Standard Path (No Split) ---
            duration = (end_time_utc - start_time_utc).total_seconds()
            status = 'overtime' if session.get('is_overtime') else 'regular'
            
            record = await cls._log_single_session(
                 user_id=member.id,
                 guild_id=session['guild_id'],
                 channel_name=session['channel_name'],
                 user_name=session['user_name'],
                 start_time=start_time_utc,
                 end_time=end_time_utc,
                 duration=duration,
                 disconnect_reason=reason,
                 status=status,
                 is_ot=session.get('is_overtime')
            )
            
            if not silent:
                print(f"[VoiceService] Session ENDED: {member.display_name} in {session['channel_name']}. Duration: {round(duration, 2)}s")
            return record
        return None

    @classmethod
    async def _log_single_session(cls, user_id, guild_id, channel_name, user_name, start_time, end_time, duration, disconnect_reason, status, is_ot):
        ist_now = get_ist_time()
        date_str = ist_now.strftime('%Y-%m-%d')
        
        await VoiceModel.append_session(
            user_id=user_id,
            guild_id=guild_id,
            date_str=date_str,
            user_name=user_name,
            session_data={
                "channel_name": channel_name,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration": round(duration, 2),
                "disconnect": disconnect_reason,
                "status": status
            },
            duration_seconds=round(duration, 2),
            is_overtime=is_ot
        )

        # Increment Global User Stats
        reg_sec = 0
        ot_sec = 0
        if is_ot:
            ot_sec = round(duration, 2)
        else:
            reg_sec = round(duration, 2)
            
        await UserModel.increment_voice_time(user_id, user_name, reg_sec, ot_sec)

        return {
            "user_id": user_id,
            "duration": duration,
            "status": status,
            "channel_name": channel_name
        }

    @classmethod
    async def trigger_auto_reconnect(cls, member, guild_id):
        """Called by AttendanceService when user DROPS."""
        # 1. If in VC, handle the switch
        if member.id in cls.active_sessions:
            current_session = cls.active_sessions[member.id]
            channel = member.guild.get_channel(current_session['channel_id'])
            
            # End current (regular) session
            await cls.end_session(member, channel, reason="auto-reconnect")
            
            # Start new (overtime) session
            if channel:
                # This will now check DB, see the 'drop' we just pushed, and set Overtime=True
                await cls.start_session(member, channel, silent=False)
                print(f"[VoiceService] Auto-reconnect triggered for {member.display_name}. Switched to OVERTIME tracking.")

    @classmethod
    async def get_statistic_data(cls, user, guild_id, start_date, end_date):
        """
        Logic for fetching and aggregating stats.
        Returns: Embed or Dict suitable for Controller to build Embed.
        For MVC, Service should return Data. Controller builds View (Embed).
        """
        user_id = user.id if user else None
        
        docs = await VoiceModel.get_stats(
            user_id=user_id,
            guild_id=guild_id,
            start_date_str=start_date.strftime('%Y-%m-%d'),
            end_date_str=end_date.strftime('%Y-%m-%d')
        )
        
        # Aggregation Logic
        # ... (Similar to original get_stats)
        # We will return the raw docs or a processed dict structure
        return docs

    @classmethod
    async def get_aggregated_stats(cls, user_id, guild_id, start_date, end_date):
        """
        Returns structured stats:
        - For single user: {total_duration, session_count, channel_stats}
        - For all (if user_id None): {global_stats (list of user summaries), ...}
        """
        user_id_query = user_id if user_id else None
        
        docs = await VoiceModel.get_stats(
            user_id=user_id_query,
            guild_id=guild_id,
            start_date_str=start_date.strftime('%Y-%m-%d'),
            end_date_str=end_date.strftime('%Y-%m-%d')
        )
        
        # Aggregate
        total_duration = 0
        session_count = 0
        channel_stats = {} 
        
        # If fetching for ALL users, we need per-user tracking
        user_stats = {} # {uid: {total, count, name}}
        
        for doc in docs:
            uid = doc['user_id']
            name = doc.get('user_name', str(uid))
            dur = doc.get('total_duration', 0)
            
            # Global totals (if single user, this matches; if all, this is grand total)
            total_duration += dur
            
            # Sessions
            sessions = doc.get('sessions', [])
            session_count += len(sessions)
            
            # Per User Stats
            if uid not in user_stats:
                user_stats[uid] = {'total_duration': 0, 'session_count': 0, 'name': name}
            
            user_stats[uid]['total_duration'] += dur
            user_stats[uid]['session_count'] += len(sessions)
            
            # Channel Stats (Only really useful for Single User view, 
            # but if specific user requested, we aggregate)
            if user_id: 
                for s in sessions:
                    c_name = s.get('channel_name', 'Unknown')
                    s_dur = s.get('duration', 0)
                    channel_stats[c_name] = channel_stats.get(c_name, 0) + s_dur

        return {
            "total_duration": total_duration,
            "session_count": session_count,
            "channel_stats": channel_stats,
            "user_stats": user_stats # Dict of per-user stats
        }
    
    @classmethod
    def format_duration(cls, seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m {s}s"
