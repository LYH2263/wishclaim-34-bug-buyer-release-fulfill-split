const ERROR_TEXT = {
  claimer_empty: '请先填写你的名字',
  claimer_dirty: '名字不合法（含控制字符或超过 32 字）',
  buyer_dirty: '代买人名字不合法（空白、控制字符或超过 32 字）',
  buyer_equal_claimer: '代买人不能与认领人是同一人',
  same_claimer: '新认领人与当前认领人相同',
  not_party: '只有认领人或代买人可以核销',
  not_claimer: '只有当前认领人可以执行此操作',
  not_claimed: '该单子当前不在认领中',
  need_claim: '需先认领才能核销',
  locked: '单子已被他人认领',
  already_fulfilled: '单子已核销',
  bad_status: '当前状态不可认领',
  'not found': '未找到该愿望',
}

export const errText = (e) => ERROR_TEXT[e.message] || e.message
