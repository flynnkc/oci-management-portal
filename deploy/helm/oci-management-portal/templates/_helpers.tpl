{{/*
Expand the name of the chart.
*/}}
{{- define "oci-management-portal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "oci-management-portal.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "oci-management-portal.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "oci-management-portal.labels" -}}
helm.sh/chart: {{ include "oci-management-portal.chart" . }}
{{ include "oci-management-portal.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Chart.AppVersion }}
app.kubernetes.io/version: {{ . | quote }}
{{- end }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "oci-management-portal.selectorLabels" -}}
app.kubernetes.io/name: {{ include "oci-management-portal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "oci-management-portal.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "oci-management-portal.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the config map to use.
*/}}
{{- define "oci-management-portal.configMapName" -}}
{{- default (include "oci-management-portal.fullname" .) .Values.config.existingConfigMap }}
{{- end }}

{{/*
Create the name of the secret to use.
*/}}
{{- define "oci-management-portal.secretName" -}}
{{- default (include "oci-management-portal.fullname" .) .Values.secret.existingSecret }}
{{- end }}
