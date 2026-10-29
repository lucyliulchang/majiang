/** 04 §2 的 user 摘要；账号与口令由 contentHub 账号服务管理，前端不持有口令哈希。 */
export interface UserInfo {
  login_id: string
  nick_name: string
  avatar_id: string
  /** 账号服务原始角色（administrator/manager/customer/...） */
  role_name: string
  /** 本系统角色 */
  role: 'admin' | 'member'
  active_flag: string
}

export interface AuthOptions {
  register_enabled: boolean
  password_reset_enabled: boolean
  verify_code_cooldown_seconds: number
}

/** 04 §3 的 family；`member_role` 是当前用户在该家庭的角色（OWNER/ADMIN/MEMBER） */
export interface FamilyInfo {
  family_code: string
  family_name: string
  owner_login_id: string
  default_rule_family_code: string | null
  default_skin_code: string | null
  member_role: string
  status: string
  sort_order: number
}

/** 04 §3 的 member */
export interface FamilyMember {
  login_id: string
  nick_name: string
  member_role: string
  member_status: string
  joined_ymdhms: string
}

/** 04 §4 的用户偏好（无任何 BGM 字段） */
export interface UserPref {
  last_family_code: string | null
  skin_code: string | null
  sound_enabled: boolean
  sound_volume: number
  chat_sound: boolean
  show_tenpai: boolean
}

export interface AuthSession {
  token: string
  user: UserInfo
  families: FamilyInfo[]
  current_family_code: string | null
}

export interface VerifyCodeResult {
  ok: boolean
  cooldown_seconds: number
  expire_seconds: number
}

export interface FanItem {
  id: string
  name: string
  fan: number
  exclusive_group: string | null
  stackable: boolean
}

export interface ThirteenUnrelatedOptions {
  enabled: boolean
  require_all_honors: boolean
  allow_pair: boolean
  min_gap: number
}

export interface PatternSwitches {
  standard: boolean
  seven_pairs: boolean
  thirteen_orphans: boolean
  thirteen_unrelated: ThirteenUnrelatedOptions
}

export interface ToggleValue {
  enabled: boolean
  value: number | null
}

export interface TurnTimeout {
  enabled: boolean
  seconds: number
}

export interface KongScore {
  enabled: boolean
  exposed: number
  hidden: number
  added: number
}

export interface RuleConfig {
  base_score: number
  fan_mode: 'linear' | 'exponential'
  fan_cap: number | null
  fan_table: FanItem[]
  patterns: PatternSwitches
  allow_chow: boolean
  turn_timeout: TurnTimeout
  kong_score: KongScore
  ting_hint: ToggleValue
  draw_penalty: ToggleValue
  discard_pay_mode: 'single' | 'all'
  dealer_continue_on_win: boolean
  dealer_continue_on_draw: boolean
  rounds_per_game: number
  claim_window_seconds: number
}

export interface RuleBrief {
  base_score: number
  fan_mode: string
  fan_cap: number | null
  allow_chow: boolean
  turn_timeout: { enabled: boolean; seconds: number | null }
  kong_score: { enabled: boolean; exposed: number; hidden: number; added: number }
  ting_hint: boolean
  patterns: string[]
  rounds_per_game: number
}

export interface RuleFamily {
  rule_family_code: string
  rule_family_name: string
  engine_code: string
  tile_set_code: string
  capability: Record<string, unknown>
  status: string
  sort_order: number
  /** 引擎细则是否已接入；false 时只可列模板，不可开桌 */
  ready: boolean
}

export interface RuleTemplate {
  id: number
  template_code: string
  /** null 表示全局预置（familyID=0） */
  family_code: string | null
  rule_family_code: string
  template_name: string
  description: string
  config: RuleConfig
  is_preset: boolean
  is_active: boolean
  owner_login_id: string | null
  created_at: string
  updated_at: string
}

export interface RoomInfo {
  id: number
  room_code: string
  family_code: string
  room_name: string
  host_login_id: string
  host_name: string
  template_id: number | null
  rule_name: string
  rule_family_code: string
  status: 'OPEN' | 'CLOSED' | string
  player_count: number
  spectator_count: number
  created_at: string
}

export interface RoomJoinCheck {
  room_code: string
  room_name: string
  host_name: string
  rule_name: string
  rule_family_code: string
  status: string
  player_count: number
  can_join: boolean
  /** 非本家庭成员：进桌要房主在牌桌上确认 */
  needs_approval?: boolean
  spectate: {
    limit_per_seat: number
    viewer_counts: number[]
    available: boolean
  }
}

/** 房主专属：非本家庭成员凭码申请进桌（S10） */
export interface JoinRequest {
  login_id: string
  display_name: string
  requested_at: number
}

export interface LegalAction {
  action: 'discard' | 'chow' | 'pong' | 'kong' | 'hu' | 'pass'
  tiles?: number[]
  kong_kind?: string
  label?: string
}

export interface MeldView {
  kind: string
  kind_name: string
  tiles: number[]
  count: number
  from_seat: number | null
  /** 副露里那张「别人打出来的牌」（吃/碰/明杠有值；暗杠/补杠为 null） */
  claim_tile?: number | null
}

export interface SeatView {
  seat: number
  login_id: string
  display_name: string
  color: string
  ready: boolean
  connected: boolean
  is_host: boolean
  hand_count: number
  melds: MeldView[]
  round_score: number
  total_score: number
  /** 本局门风 0–3（庄家恒为 0=东），04 §9.5 */
  wind?: number
  is_dealer?: boolean
  /** 当前围观人数（0–10），全房可见、不含观战者身份 */
  spectator_count?: number
}

/** 观战视角：同一时刻只跟随 1 名在座玩家（S5b） */
export interface SpectateView {
  target_seat: number | null
  target_login_id: string
  viewer_count: number
  limit_per_seat: number
}

export interface FanLine {
  id: string
  name: string
  fan: number
  count: number
}

export interface RoundResult {
  round_no: number
  winner_seat: number | null
  win_type: string
  winning_tile: number | null
  pattern_id: string | null
  fan_total: number
  fan_items: FanLine[]
  score_delta: number[]
  breakdown: { pattern_name: string; lines: FanLine[]; fan_raw: number; fan_total: number; capped: boolean } | null
  is_last_round?: boolean
  /** 本局累计杠分（四家，下标即座位）；番分之外的加减分 */
  kong_delta?: number[]
  /** 生效倍数：自摸 ×2、庄家份 ×2（柏氏）；其它族恒为 1 */
  multipliers?: { self_draw: number; dealer: number }
  summary_text?: string
}

export interface Snapshot {
  room: {
    room_code: string
    room_name: string
    host_login_id: string
    family_code: string
    family_name: string
    rule_name: string
    rule_family_code: string
    rule_brief: RuleBrief
    spectator_count?: number
    seat_viewer_counts?: number[]
    /** 兼容别名（S6 前端切完后删除） */
    code?: string
    name?: string
  }
  self_seat: number | null
  /** 在座玩家恒为 null；观战者已选目标时有值 */
  spectate: SpectateView | null
  /** 房主专属：等待确认的进桌申请（其他人恒为空数组） */
  join_requests?: JoinRequest[]
  seats: (SeatView | null)[]
  status: string
  round_no: number
  /** 本局局风 0 东 / 1 南 / 2 西 / 3 北 = round_no - 1（04 §9.5） */
  round_wind?: number
  dealer_seat: number | null
  /** 暂停态（增量字段，缺省视为未暂停） */
  paused?: { paused: boolean; by_seat: number | null; note: string | null }
  game_total_rounds: number
  hand: number[]
  drawn: number | null
  turn: number | null
  phase: string
  wall_count: number
  discards: number[][]
  last_discard: { seat: number; tile: number } | null
  legal: { actions: LegalAction[]; claim_tile?: number; claim_from?: number; reason?: string }
  tenpai: Record<string, number[]>
  deadline: number | null
  claim_deadline: number | null
  result: RoundResult | null
}

export interface ChatMessage {
  id: number
  room_id?: number
  /** 系统播报为 null；账号身份是 loginID 字符串 */
  login_id: string | null
  kind: 'chat' | 'system'
  content: string
  created_at: string
  user_name?: string
}

export interface GameSummary {
  id: number
  /** 这场牌所属家庭；与当前家庭不同即为客队场次 */
  family_code?: string
  family_name?: string
  room_name: string
  rule_name: string
  status: string
  started_at: string
  ended_at: string | null
  my_score: number
  players: { seat: number; login_id: string; display_name: string; color: string; total_score: number }[]
}

export interface GameDetail {
  id: number
  family_code?: string
  family_name?: string
  room_name: string
  rule_name: string
  rule_snapshot: RuleConfig
  status: string
  started_at: string
  ended_at: string | null
  players: { seat: number; login_id: string; display_name: string; color: string; total_score: number }[]
  rounds: {
    round_no: number
    dealer_seat: number
    winner_seat: number | null
    win_type: string
    winning_tile_name: string | null
    pattern_id: string | null
    fan_items: FanLine[]
    fan_total: number
    score_delta: number[]
    /** 终局四家手牌与副露（旧局为空数组），用于核对番种 */
    final_hands: {
      seat: number
      login_id?: string
      display_name: string
      concealed: number[]
      melds: {
        kind: string
        kind_name: string
        tiles: number[]
        from_seat: number | null
        claim_tile: number | null
      }[]
      is_winner: boolean
      win_type: string | null
      winning_tile: number | null
    }[]
  }[]
}

export interface StatsInfo {
  total_score: number
  games_played: number
  best_game: number
  worst_game: number
  rounds_won: number
}

/** 04 §8 的 skin；`family_code` 为 null 表示全局内置皮肤 */
export interface SkinInfo {
  skin_code: string
  skin_name: string
  family_code: string | null
  is_default: boolean
  status: string
  tile_aspect: number
  asset_count: number
  preview_url: string | null
  /** tile_key → 绝对 URL（`/majiangapp/tiles/...`），缺项表示该张使用内置矢量牌面 */
  assets: Record<string, string>
  fallback: string
  updated_at: string
}

/** PUT /api/skins/{skin_code}/{tile_key} 的响应 */
export interface SkinAssetInfo {
  tile_key: string
  file_id: string
  width: number
  height: number
}

/** GET /api/rules/validate 的响应（试算，不落库） */
export interface RuleValidateResult {
  ok: boolean
  code: string
  message: string
  summary: string
}
