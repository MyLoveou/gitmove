import type { MemberStatus } from '../../shared/protocol'

/** pin 可能是完整哈希或前缀。分支名、空 pin 不当成「落后」。 */
export function commitsMatch(head: string | null | undefined, pin: string | null | undefined): boolean {
  if (!head || !pin) return true
  const left = head.toLowerCase()
  const right = pin.toLowerCase()
  if (left === right) return true
  if (/^[0-9a-f]{7,}$/.test(right) && (left.startsWith(right) || right.startsWith(left))) return true
  return false
}

export function memberDrift(member: Pick<MemberStatus, 'head' | 'pin' | 'dirty' | 'missing'>): boolean {
  if (member.missing || member.dirty) return true
  return !commitsMatch(member.head, member.pin)
}
