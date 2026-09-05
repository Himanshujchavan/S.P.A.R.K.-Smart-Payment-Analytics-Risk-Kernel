// Audit trail page — every decision, with its trigger and the reasoning
// that produced it. Filterable; exportable for compliance.

import AuditTrailViewer from '../../components/AuditTrailViewer'
import { PageHeader } from '../../components/Primitives'

export default function AuditPage() {
  return (
    <div>
      <PageHeader
        title="Audit trail"
        subtitle="Every decision S.P.A.R.K. has made — with the reasoning behind it."
      />
      <AuditTrailViewer />
    </div>
  )
}
