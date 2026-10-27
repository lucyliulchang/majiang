export interface UserInfo {
  id: number
  username: string
  display_name: string
  role: 'admin' | 'member'
  color: string
  is_active: boolean
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

export interface RuleTemplate {
  id: number
  owner_id: number | null
  name: string
  description: string
  config: RuleConfig
  is_preset: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface RoomInfo {
  id: number
  code: string
  name: string
  host_id: number
  host_name: string
  rule_template_id: number | null
  rule_name: string
  status: string
  created_at: string
  player_count: number
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
}

export interface SeatView {
  seat: number
  user_id: number
  display_name: string
  color: string
  ready: boolean
  connected: boolean
  is_host: boolean
  hand_count: number
  melds: MeldView[]
  round_score: number
  total_score: number
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
}

export interface Snapshot {
  room: {
    code: string
    name: string
    host_id: number
    rule_name: string
    rule_brief: RuleBrief
  }
  self_seat: number | null
  seats: (SeatView | null)[]
  status: string
  round_no: number
  dealer_seat: number | null
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
  user_id: number | null
  kind: 'chat' | 'system'
  content: string
  created_at: string
  user_name?: string
}

export interface GameSummary {
  id: number
  room_name: string
  status: string
  started_at: string
  ended_at: string | null
  my_score: number
  players: { seat: number; user_id: number; display_name: string; color: string; total_score: number }[]
}

export interface GameDetail {
  id: number
  room_name: string
  rule_name: string
  rule_snapshot: RuleConfig
  status: string
  started_at: string
  ended_at: string | null
  players: { seat: number; user_id: number; display_name: string; color: string; total_score: number }[]
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
  }[]
}

export interface StatsInfo {
  total_score: number
  games_played: number
  best_game: number
  worst_game: number
  rounds_won: number
}
