from datetime import datetime, timezone
from models.voice_model import VoiceModel
from utils.time_utils import get_ist_time

class VoiceService:
    # State Management (Singleton-like behavior via class attributes)
    active_sessions = {} # {member_id: session_data}
    overtime_users = set() # {member_id}

    @classmethod
    def is_user_in_overtime(cls, member_id, guild_id):
        return (member_id, guild_id) in cls.overtime_users

    @classmethod
    def start_session(cls, member, channel, silent=False):
        # Force Overtime on Weekends
        if get_ist_time().weekday() >= 5:
            is_overtime = True
        else:
            is_overtime = cls.is_user_in_overtime(member.id, channel.guild.id)
        
        cls.active_sessions[member.id] = {
            'start_time': datetime.now(timezone.utc),
            'channel_id': channel.id,
            'channel_name': channel.name,
            'guild_id': channel.guild.id,
            'user_name': member.display_name,
            'is_overtime': is_overtime
        }
        
        if not silent:
            status_msg = " [OVERTIME]" if is_overtime else ""
            print(f"[VoiceService] Session STARTED: {member.display_name} in {channel.name}{status_msg}")

    @classmethod
    async def end_session(cls, member, channel, reason="left", silent=False):
        if member.id in cls.active_sessions:
            session = cls.active_sessions.pop(member.id)
            
            start_time = session['start_time']
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            # Prepare record for DB
            record = {
                'user_id': member.id,
                'user_name': session['user_name'],
                'channel_id': session['channel_id'],
                'channel_name': session['channel_name'],
                'guild_id': session['guild_id'],
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': round(duration, 2),
                'disconnect': reason,
                'status': 'overtime' if session.get('is_overtime') else 'regular'
            }
            
            ist_now = get_ist_time()
            date_str = ist_now.strftime('%Y-%m-%d')
            
            # Call Model
            await VoiceModel.append_session(
                user_id=record['user_id'],
                guild_id=record['guild_id'],
                date_str=date_str,
                user_name=record['user_name'],
                session_data={
                    "channel_name": record['channel_name'],
                    "start_time": record['start_time'],
                    "end_time": record['end_time'],
                    "duration": record['duration_seconds'],
                    "disconnect": reason,
                    "status": record['status']
                },
                duration_seconds=record['duration_seconds'],
                is_overtime=(record['status'] == 'overtime')
            )
            
            if not silent:
                print(f"[VoiceService] Session ENDED: {member.display_name} in {session['channel_name']}. Duration: {round(duration, 2)}s")
            return record
        return None

    @classmethod
    async def trigger_auto_disconnect(cls, member, guild_id):
        """Called by AttendanceService when user DROPS."""
        # 1. Mark user as overtime (scoped to guild)
        cls.overtime_users.add((member.id, guild_id))
        
        # 2. If in VC, handle the switch
        if member.id in cls.active_sessions:
            current_session = cls.active_sessions[member.id]
            channel = member.guild.get_channel(current_session['channel_id'])
            
            # End current (regular) session
            await cls.end_session(member, channel, reason="auto-disconnect")
            
            # Start new (overtime) session
            if channel:
                cls.start_session(member, channel, silent=False)
                print(f"[VoiceService] Auto-disconnect triggered for {member.display_name}. Switched to OVERTIME tracking.")

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
