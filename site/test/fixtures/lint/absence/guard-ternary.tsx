// fixture: a ternary on the value itself, so 0 renders as the fallback (lint_absence: guard)
export const Cell = ({ score }: { score?: number }) => <td>{score ? score : 'not reported'}</td>;
