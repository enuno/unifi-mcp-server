{{/* Names and labels. */}}
{{- define "unifi-mcp.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "unifi-mcp.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "unifi-mcp.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "unifi-mcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "unifi-mcp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "unifi-mcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "unifi-mcp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "unifi-mcp.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "unifi-mcp.image" -}}
{{- $tag := .Values.image.tag | default (printf "%s%s" .Chart.AppVersion (ternary "-fleet" "" .Values.fleet.enabled)) -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end -}}

{{/* Fail early on settings that cannot work together. */}}
{{- define "unifi-mcp.validate" -}}
{{- if not .Values.existingSecret -}}
{{- fail "existingSecret is required: a Secret holding UNIFI_API_KEY, MCP_AUTH_TOKEN and UNIFI_AUDIT_CHAIN_KEY (values.yaml)" -}}
{{- end -}}
{{- if and (eq .Values.controller.apiType "local") (not .Values.controller.localHost) -}}
{{- fail "controller.localHost is required when controller.apiType is local" -}}
{{- end -}}
{{- if not (has .Values.controller.apiType (list "local" "cloud-v1" "cloud-ea")) -}}
{{- fail "controller.apiType must be local, cloud-v1 or cloud-ea" -}}
{{- end -}}
{{- if and .Values.persistence.enabled (gt (int .Values.server.replicas) 1) -}}
{{- fail "persistence uses one ReadWriteOnce volume: keep server.replicas at 1, or use fleet.enabled (the audit log then lives in Postgres)" -}}
{{- end -}}
{{- if and .Values.audit.retentionDays (not .Values.fleet.enabled) -}}
{{- fail "audit.retentionDays runs the Postgres retention job and needs fleet.enabled; without fleet use audit.rotateMb and a SIEM copy" -}}
{{- end -}}
{{- range $name, $_ := .Values.server.extraEnv -}}
{{- if has $name (list "UNIFI_API_KEY" "MCP_AUTH_TOKEN" "UNIFI_AUDIT_CHAIN_KEY" "UNIFI_AUDIT_LOG_KEY" "UNIFI_FLEET_CREDENTIAL_KEY" "DATABASE_URL" "MIGRATION_DATABASE_URL" "REDIS_URL" "UNIFI_AUDIT_SIEM_WEBHOOK_SECRET" "UNIFI_AUDIT_SIEM_OTLP_HEADERS") -}}
{{- fail (printf "server.extraEnv.%s is a secret: put it in existingSecret instead" $name) -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* The env every server and worker container gets, besides the Secret. */}}
{{- define "unifi-mcp.env" -}}
{{- $replicas := int .Values.server.replicas -}}
{{- $workers := ternary (int .Values.fleet.workers.replicas) 0 .Values.fleet.enabled -}}
{{- $env := dict
  "UNIFI_API_TYPE" .Values.controller.apiType
  "UNIFI_LOCAL_HOST" .Values.controller.localHost
  "UNIFI_LOCAL_PORT" (toString .Values.controller.localPort)
  "UNIFI_LOCAL_VERIFY_SSL" (toString .Values.controller.verifySsl)
  "MCP_SERVER_TRANSPORT" "streamable_http"
  "MCP_SERVER_HOST" "0.0.0.0"
  "MCP_SERVER_PORT" "3000"
  "MCP_STATELESS_HTTP" (toString .Values.server.statelessHttp)
  "UNIFI_METRICS_ENABLED" (toString .Values.server.metrics)
  "UNIFI_AUDIT_LOG_PATH" "/app/logs/audit.log"
  "UNIFI_AUDIT_LOG_ROTATE_MB" (toString .Values.audit.rotateMb)
  "UNIFI_AUDIT_RETENTION_DAYS" (toString .Values.audit.retentionDays)
  "UNIFI_AUDIT_ARCHIVE_DIR" (ternary "/app/archive" "" .Values.fleet.enabled)
  "UNIFI_AUDIT_SIEM_TARGETS" .Values.audit.siemTargets
  "UNIFI_AUDIT_SIEM_CA_FILE" .Values.audit.siemCaFile
  "UNIFI_AUDIT_SIEM_BUFFER_DIR" "/app/logs/siem-buffer"
  "UNIFI_FLEET_EXPECTED_REPLICAS" (toString (add $replicas $workers))
-}}
{{- $env = merge (dict) .Values.server.extraEnv $env -}}
{{- range $name := keys $env | sortAlpha }}
{{- $value := toString (get $env $name) }}
{{- if $value }}
- name: {{ $name }}
  value: {{ $value | quote }}
{{- end }}
{{- end }}
{{- end -}}

{{- define "unifi-mcp.envFrom" -}}
- secretRef:
    name: {{ .Values.existingSecret }}
{{- end -}}
