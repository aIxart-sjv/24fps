import type {
  ActivityEvent,
  AcquisitionJob,
  AdminUser,
  AIInsight,
  AIServiceStatus,
  BlockchainAnchor,
  Case,
  CorrelationEvent,
  CustodyEvent,
  DetectionEvent,
  Device,
  Evidence,
  IntegrityAlert,
  Recording,
  ReviewStatus,
  RecoveryReport,
  Report,
  SecurityEvent,
  SystemService,
  TimelineEvent,
  ValidationCheck,
  VendorProfile,
  VerificationEvent,
} from '@/services/types'

/**
 * All mock data below is static and deterministic (no Math.random) so that
 * the demo stays internally consistent across renders and page reloads.
 */

function seededHex(seed: string, length: number): string {
  const chars = '0123456789abcdef'
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  let state = h || 1
  let out = ''
  for (let i = 0; i < length; i++) {
    state = (state * 1103515245 + 12345) >>> 0
    // Use the high-order bits — an LCG's low-order bits cycle with very short, poor periods.
    out += chars[(state >>> 28) & 0xf]
  }
  return out
}

const sha256For = (seed: string) => seededHex(`${seed}:sha256`, 64)
const md5For = (seed: string) => seededHex(`${seed}:md5`, 32)

export const INVESTIGATORS = [
  'Insp. R. Mehta',
  'Insp. A. Fernandes',
  'Insp. S. Kulkarni',
  'Insp. N. Rao',
  'Insp. P. Singh',
] as const

// ---------------------------------------------------------------------------
// Cases
// ---------------------------------------------------------------------------

export const CASES: Case[] = [
  {
    id: 'CASE-2026-014',
    name: 'Highway Incident Investigation',
    description:
      'Multi-vehicle collision on NH-48 with suspected reckless driving. CCTV and DVR footage from three roadside units is under forensic review to reconstruct the sequence of events and identify the vehicle that fled the scene.',
    priority: 'High',
    status: 'Active',
    leadInvestigator: 'Insp. R. Mehta',
    createdAt: '2026-08-21T09:10:00',
    updatedAt: '2026-08-27T09:58:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'Complete' },
      { label: 'Media Processing', status: 'In Progress' },
      { label: 'AI Analysis', status: 'In Progress' },
      { label: 'Final Review', status: 'Pending' },
    ],
  },
  {
    id: 'CASE-2026-013',
    name: 'Warehouse Theft Investigation',
    description:
      'Repeated inventory loss at a logistics warehouse. Internal NVR footage and access logs are being cross-referenced against staff shift records to identify the point of entry.',
    priority: 'Medium',
    status: 'Under Review',
    leadInvestigator: 'Insp. A. Fernandes',
    createdAt: '2026-08-14T11:20:00',
    updatedAt: '2026-08-25T16:40:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'Complete' },
      { label: 'Media Processing', status: 'Complete' },
      { label: 'AI Analysis', status: 'Complete' },
      { label: 'Final Review', status: 'In Progress' },
    ],
  },
  {
    id: 'CASE-2026-012',
    name: 'Residential Burglary Series',
    description:
      'Series of five break-ins across a residential sector sharing a common entry method. Doorbell camera footage and mobile device extractions from witnesses are being consolidated.',
    priority: 'Medium',
    status: 'Active',
    leadInvestigator: 'Insp. S. Kulkarni',
    createdAt: '2026-08-10T08:05:00',
    updatedAt: '2026-08-26T14:12:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'Complete' },
      { label: 'Media Processing', status: 'In Progress' },
      { label: 'AI Analysis', status: 'Pending' },
      { label: 'Final Review', status: 'Pending' },
    ],
  },
  {
    id: 'CASE-2026-011',
    name: 'Corporate Data Breach',
    description:
      'Unauthorized access to internal file servers traced to a compromised employee endpoint. Forensic disk images and a seized mobile device are undergoing full acquisition and hash verification.',
    priority: 'Critical',
    status: 'Active',
    leadInvestigator: 'Insp. N. Rao',
    createdAt: '2026-08-19T13:30:00',
    updatedAt: '2026-08-27T08:15:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'In Progress' },
      { label: 'Media Processing', status: 'Pending' },
      { label: 'AI Analysis', status: 'Pending' },
      { label: 'Final Review', status: 'Pending' },
    ],
  },
  {
    id: 'CASE-2026-010',
    name: 'Missing Person Case',
    description:
      'Last known location established via cell tower triangulation and forecourt CCTV. Forensic image acquired from a recovered mobile device is under active review for location and contact metadata.',
    priority: 'Critical',
    status: 'Under Review',
    leadInvestigator: 'Insp. P. Singh',
    createdAt: '2026-08-05T07:45:00',
    updatedAt: '2026-08-24T19:05:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'Complete' },
      { label: 'Media Processing', status: 'Complete' },
      { label: 'AI Analysis', status: 'In Progress' },
      { label: 'Final Review', status: 'Pending' },
    ],
  },
  {
    id: 'CASE-2026-009',
    name: 'Vehicle Theft Ring',
    description:
      'Organized vehicle theft operation linked across four separate incidents. DVR footage from parking structures is being analyzed for a recurring vehicle and license plate matches.',
    priority: 'High',
    status: 'Active',
    leadInvestigator: 'Insp. R. Mehta',
    createdAt: '2026-07-30T10:00:00',
    updatedAt: '2026-08-23T12:50:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'Complete' },
      { label: 'Media Processing', status: 'In Progress' },
      { label: 'AI Analysis', status: 'In Progress' },
      { label: 'Final Review', status: 'Pending' },
    ],
  },
  {
    id: 'CASE-2026-008',
    name: 'Assault Investigation',
    description:
      'Altercation outside a commercial premises captured on a single fixed camera. Case closed following successful identification and corroborating witness statements.',
    priority: 'Low',
    status: 'Closed',
    leadInvestigator: 'Insp. A. Fernandes',
    createdAt: '2026-07-12T15:20:00',
    updatedAt: '2026-08-01T09:30:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'Complete' },
      { label: 'Media Processing', status: 'Complete' },
      { label: 'AI Analysis', status: 'Complete' },
      { label: 'Final Review', status: 'Complete' },
    ],
  },
  {
    id: 'CASE-2026-007',
    name: 'Fraud Investigation',
    description:
      'Financial fraud case built on document evidence and transaction records. Closed and archived pending appeal window.',
    priority: 'Medium',
    status: 'Closed',
    leadInvestigator: 'Insp. S. Kulkarni',
    createdAt: '2026-06-28T09:00:00',
    updatedAt: '2026-07-20T11:10:00',
    progress: [
      { label: 'Evidence Registration', status: 'Complete' },
      { label: 'Integrity Verification', status: 'Complete' },
      { label: 'Media Processing', status: 'Complete' },
      { label: 'AI Analysis', status: 'Complete' },
      { label: 'Final Review', status: 'Complete' },
    ],
  },
]

// ---------------------------------------------------------------------------
// Devices
// ---------------------------------------------------------------------------

export const DEVICES: Device[] = [
  {
    id: 'DVR-UNIT-03',
    type: 'CCTV DVR',
    manufacturer: 'Hikvision',
    model: 'DS-7204HUHI-K1',
    firmware: 'V4.30.014',
    serialNumber: 'HK7204-88213',
    channelCount: 4,
    cameraCount: 4,
    identificationMethod: 'Firmware Signature Match',
    identificationConfidence: 0.97,
    status: 'Online',
    storageTotal: 4_000_000_000_000,
    storageUsed: 2_940_000_000_000,
    lastActivity: '2026-08-27T10:31:00',
    caseId: 'CASE-2026-014',
    acquisitionHistory: [
      { timestamp: '2026-08-21T09:40:00', action: 'Device registered to case' },
      { timestamp: '2026-08-21T09:52:00', action: 'Recording index acquired' },
      { timestamp: '2026-08-27T10:31:00', action: 'New recording registered' },
    ],
  },
  {
    id: 'NVR-UNIT-07',
    type: 'NVR',
    manufacturer: 'Dahua',
    model: 'NVR4208-8P',
    firmware: 'V4.001.0000000.2',
    serialNumber: 'DH4208-55019',
    channelCount: 8,
    cameraCount: 6,
    identificationMethod: 'Protocol Fingerprint (ONVIF)',
    identificationConfidence: 0.94,
    status: 'Online',
    storageTotal: 8_000_000_000_000,
    storageUsed: 3_120_000_000_000,
    lastActivity: '2026-08-27T08:02:00',
    caseId: 'CASE-2026-014',
    acquisitionHistory: [
      { timestamp: '2026-08-21T10:05:00', action: 'Device registered to case' },
      { timestamp: '2026-08-22T14:18:00', action: 'Channel export completed' },
    ],
  },
  {
    id: 'CAM-UNIT-04',
    type: 'Camera',
    manufacturer: 'Axis',
    model: 'P3245-LVE',
    firmware: '10.12.106',
    serialNumber: 'AX3245-30841',
    channelCount: 1,
    cameraCount: 1,
    identificationMethod: 'Vendor SDK Handshake',
    identificationConfidence: 0.99,
    status: 'Analyzing',
    storageTotal: 256_000_000_000,
    storageUsed: 198_000_000_000,
    lastActivity: '2026-08-27T10:12:00',
    caseId: 'CASE-2026-014',
    acquisitionHistory: [
      { timestamp: '2026-08-21T11:00:00', action: 'Device registered to case' },
      { timestamp: '2026-08-27T10:12:00', action: 'AI analysis started' },
    ],
  },
  {
    id: 'DVR-UNIT-05',
    type: 'CCTV DVR',
    manufacturer: 'Hikvision',
    model: 'DS-7208HQHI-K2',
    firmware: 'V4.02.024',
    serialNumber: 'HK7208-41027',
    channelCount: 8,
    cameraCount: 8,
    identificationMethod: 'Firmware Signature Match',
    identificationConfidence: 0.95,
    status: 'Offline',
    storageTotal: 2_000_000_000_000,
    storageUsed: 1_870_000_000_000,
    lastActivity: '2026-08-25T16:40:00',
    caseId: 'CASE-2026-013',
    acquisitionHistory: [
      { timestamp: '2026-08-14T12:00:00', action: 'Device registered to case' },
      { timestamp: '2026-08-25T16:40:00', action: 'Device went offline' },
    ],
  },
  {
    id: 'MOB-UNIT-01',
    type: 'Mobile Device',
    manufacturer: 'Apple',
    model: 'iPhone 13',
    firmware: 'iOS 17.4.1',
    serialNumber: 'C39-XJ0271',
    channelCount: 0,
    cameraCount: 0,
    identificationMethod: 'Manual Entry (Physical Inspection)',
    identificationConfidence: 1,
    status: 'Online',
    storageTotal: 128_000_000_000,
    storageUsed: 96_000_000_000,
    lastActivity: '2026-08-27T08:15:00',
    caseId: 'CASE-2026-011',
    acquisitionHistory: [
      { timestamp: '2026-08-19T14:00:00', action: 'Device seized and logged' },
      { timestamp: '2026-08-20T09:30:00', action: 'Full extraction completed' },
    ],
  },
  {
    id: 'STOR-UNIT-02',
    type: 'Storage Device',
    manufacturer: 'Seagate',
    model: 'Exos X18',
    firmware: 'SN04',
    serialNumber: 'ZL2R9Q4X',
    channelCount: 0,
    cameraCount: 0,
    identificationMethod: 'Manual Entry (Physical Inspection)',
    identificationConfidence: 1,
    status: 'Online',
    storageTotal: 18_000_000_000_000,
    storageUsed: 14_200_000_000_000,
    lastActivity: '2026-08-27T07:50:00',
    caseId: 'CASE-2026-011',
    acquisitionHistory: [
      { timestamp: '2026-08-19T15:10:00', action: 'Forensic image acquired' },
      { timestamp: '2026-08-19T18:44:00', action: 'SHA-256 verification completed' },
    ],
  },
  {
    id: 'IMG-UNIT-01',
    type: 'Forensic Image Source',
    manufacturer: 'Cellebrite',
    model: 'UFED Touch2',
    firmware: '7.62.1',
    serialNumber: 'UFED-77213',
    channelCount: 0,
    cameraCount: 0,
    identificationMethod: 'Vendor SDK Handshake',
    identificationConfidence: 0.98,
    status: 'Online',
    storageTotal: 1_000_000_000_000,
    storageUsed: 412_000_000_000,
    lastActivity: '2026-08-24T19:05:00',
    caseId: 'CASE-2026-010',
    acquisitionHistory: [
      { timestamp: '2026-08-05T08:20:00', action: 'Device registered to case' },
      { timestamp: '2026-08-06T10:00:00', action: 'Mobile image acquired' },
    ],
  },
  {
    id: 'DVR-UNIT-08',
    type: 'CCTV DVR',
    manufacturer: 'CP Plus',
    model: 'CP-UVR-0801E1',
    firmware: 'V2.8.3 build 210415',
    serialNumber: 'CPP0801-19284',
    channelCount: 8,
    cameraCount: 5,
    identificationMethod: 'Firmware Signature Match',
    identificationConfidence: 0.62,
    status: 'Error',
    storageTotal: 1_000_000_000_000,
    storageUsed: 940_000_000_000,
    lastActivity: '2026-08-23T12:50:00',
    caseId: 'CASE-2026-009',
    acquisitionHistory: [
      { timestamp: '2026-07-30T10:30:00', action: 'Device registered to case' },
      { timestamp: '2026-08-23T12:50:00', action: 'Acquisition error: disk read failure' },
    ],
  },
  {
    id: 'CAM-UNIT-09',
    type: 'Camera',
    manufacturer: 'Hikvision',
    model: 'DS-2CD2043G2-I',
    firmware: 'V5.7.3',
    serialNumber: 'HK2043-60214',
    channelCount: 1,
    cameraCount: 1,
    identificationMethod: 'Firmware Signature Match',
    identificationConfidence: 0.98,
    status: 'Online',
    storageTotal: 512_000_000_000,
    storageUsed: 88_000_000_000,
    lastActivity: '2026-08-26T14:12:00',
    caseId: 'CASE-2026-012',
    acquisitionHistory: [
      { timestamp: '2026-08-10T08:40:00', action: 'Device registered to case' },
    ],
  },
  {
    id: 'NVR-UNIT-10',
    type: 'NVR',
    manufacturer: 'Uniview',
    model: 'NVR301-08S2',
    firmware: 'V4.19.0',
    serialNumber: 'UNV301-08872',
    channelCount: 8,
    cameraCount: 8,
    identificationMethod: 'Protocol Fingerprint (ONVIF)',
    identificationConfidence: 0.91,
    status: 'Offline',
    storageTotal: 4_000_000_000_000,
    storageUsed: 3_980_000_000_000,
    lastActivity: '2026-07-20T11:10:00',
    caseId: 'CASE-2026-007',
    acquisitionHistory: [
      { timestamp: '2026-06-28T09:20:00', action: 'Device registered to case' },
      { timestamp: '2026-07-20T11:10:00', action: 'Case closed — device archived' },
    ],
  },
]

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------

function verificationHistoryFor(registeredAt: string, sha256Status: string, md5Status: string): VerificationEvent[] {
  const history: VerificationEvent[] = [
    { timestamp: registeredAt, label: 'Evidence registered', algorithm: null, result: 'Success' },
  ]
  if (md5Status !== 'Pending') {
    history.push({
      timestamp: addMinutes(registeredAt, 2),
      label: 'MD5 verified successfully',
      algorithm: 'MD5',
      result: md5Status === 'Failed' ? 'Failure' : 'Success',
    })
  }
  if (sha256Status !== 'Pending') {
    history.push({
      timestamp: addMinutes(registeredAt, 3),
      label: 'SHA-256 verified successfully',
      algorithm: 'SHA-256',
      result: sha256Status === 'Failed' ? 'Failure' : 'Success',
    })
  }
  return history.reverse()
}

function addMinutes(iso: string, minutes: number): string {
  const d = new Date(iso)
  d.setMinutes(d.getMinutes() + minutes)
  return d.toISOString().slice(0, 19)
}

interface EvidenceSeed {
  id: string
  caseId: string
  sourceType: Evidence['sourceType']
  fileName: string
  originalSource: string
  fileSize: number
  registeredAt: string
  registeredBy: string
  status: Evidence['status']
  sha256Status: Evidence['sha256Status']
  md5Status: Evidence['md5Status']
}

const EVIDENCE_SEEDS: EvidenceSeed[] = [
  { id: 'EVID-00482', caseId: 'CASE-2026-014', sourceType: 'Forensic Image', fileName: 'highway_dvr.img', originalSource: 'DVR-UNIT-03', fileSize: 128_400_000_000, registeredAt: '2026-08-27T10:18:00', registeredBy: 'Insp. R. Mehta', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00483', caseId: 'CASE-2026-014', sourceType: 'CCTV Recording', fileName: 'cam04_2026-08-21.mp4', originalSource: 'CAM-UNIT-04', fileSize: 4_200_000_000, registeredAt: '2026-08-21T11:05:00', registeredBy: 'Insp. R. Mehta', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00484', caseId: 'CASE-2026-014', sourceType: 'CCTV Recording', fileName: 'nvr07_channel02.mp4', originalSource: 'NVR-UNIT-07', fileSize: 3_800_000_000, registeredAt: '2026-08-22T14:20:00', registeredBy: 'Insp. R. Mehta', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00485', caseId: 'CASE-2026-014', sourceType: 'Photograph', fileName: 'scene_overview_01.jpg', originalSource: 'Field capture', fileSize: 8_400_000, registeredAt: '2026-08-21T09:30:00', registeredBy: 'Insp. R. Mehta', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00491', caseId: 'CASE-2026-014', sourceType: 'CCTV Recording', fileName: 'cam04_plate_capture.mp4', originalSource: 'CAM-UNIT-04', fileSize: 2_100_000_000, registeredAt: '2026-08-26T18:40:00', registeredBy: 'Insp. R. Mehta', status: 'Active', sha256Status: 'Pending', md5Status: 'Verified' },
  { id: 'EVID-00471', caseId: 'CASE-2026-013', sourceType: 'CCTV Recording', fileName: 'warehouse_dvr05_entry.mp4', originalSource: 'DVR-UNIT-05', fileSize: 1_900_000_000, registeredAt: '2026-08-14T12:15:00', registeredBy: 'Insp. A. Fernandes', status: 'Flagged', sha256Status: 'Warning', md5Status: 'Verified' },
  { id: 'EVID-00460', caseId: 'CASE-2026-013', sourceType: 'Document', fileName: 'staff_shift_log_august.pdf', originalSource: 'HR records', fileSize: 2_400_000, registeredAt: '2026-08-14T13:00:00', registeredBy: 'Insp. A. Fernandes', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00461', caseId: 'CASE-2026-013', sourceType: 'CCTV Recording', fileName: 'warehouse_dvr05_loading.mp4', originalSource: 'DVR-UNIT-05', fileSize: 2_600_000_000, registeredAt: '2026-08-15T08:20:00', registeredBy: 'Insp. A. Fernandes', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00455', caseId: 'CASE-2026-012', sourceType: 'CCTV Recording', fileName: 'doorbell_cam09_clip01.mp4', originalSource: 'CAM-UNIT-09', fileSize: 640_000_000, registeredAt: '2026-08-10T09:00:00', registeredBy: 'Insp. S. Kulkarni', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00456', caseId: 'CASE-2026-012', sourceType: 'Mobile Extraction', fileName: 'witness_phone_extract.zip', originalSource: 'Witness device', fileSize: 5_100_000_000, registeredAt: '2026-08-11T10:40:00', registeredBy: 'Insp. S. Kulkarni', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00457', caseId: 'CASE-2026-012', sourceType: 'Photograph', fileName: 'entry_point_damage.jpg', originalSource: 'Field capture', fileSize: 6_200_000, registeredAt: '2026-08-12T08:15:00', registeredBy: 'Insp. S. Kulkarni', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00458', caseId: 'CASE-2026-012', sourceType: 'CCTV Recording', fileName: 'doorbell_cam09_clip02.mp4', originalSource: 'CAM-UNIT-09', fileSize: 580_000_000, registeredAt: '2026-08-13T19:22:00', registeredBy: 'Insp. S. Kulkarni', status: 'Active', sha256Status: 'Pending', md5Status: 'Pending' },
  { id: 'EVID-00459', caseId: 'CASE-2026-012', sourceType: 'Document', fileName: 'incident_report_burglary_03.pdf', originalSource: 'Field report', fileSize: 1_100_000, registeredAt: '2026-08-14T09:05:00', registeredBy: 'Insp. S. Kulkarni', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00475', caseId: 'CASE-2026-011', sourceType: 'Forensic Image', fileName: 'fileserver_disk01.img', originalSource: 'STOR-UNIT-02', fileSize: 512_000_000_000, registeredAt: '2026-08-19T15:12:00', registeredBy: 'Insp. N. Rao', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00476', caseId: 'CASE-2026-011', sourceType: 'Mobile Extraction', fileName: 'employee_endpoint_extract.zip', originalSource: 'MOB-UNIT-01', fileSize: 68_000_000_000, registeredAt: '2026-08-20T09:35:00', registeredBy: 'Insp. N. Rao', status: 'Active', sha256Status: 'Pending', md5Status: 'Verified' },
  { id: 'EVID-00477', caseId: 'CASE-2026-011', sourceType: 'Document', fileName: 'access_log_export.csv', originalSource: 'Internal audit', fileSize: 9_800_000, registeredAt: '2026-08-19T16:00:00', registeredBy: 'Insp. N. Rao', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00478', caseId: 'CASE-2026-011', sourceType: 'Forensic Image', fileName: 'fileserver_disk02.img', originalSource: 'STOR-UNIT-02', fileSize: 498_000_000_000, registeredAt: '2026-08-20T11:00:00', registeredBy: 'Insp. N. Rao', status: 'Active', sha256Status: 'Warning', md5Status: 'Verified' },
  { id: 'EVID-00440', caseId: 'CASE-2026-010', sourceType: 'Forensic Image', fileName: 'missing_person_phone.img', originalSource: 'IMG-UNIT-01', fileSize: 118_000_000_000, registeredAt: '2026-08-06T10:10:00', registeredBy: 'Insp. P. Singh', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00441', caseId: 'CASE-2026-010', sourceType: 'Document', fileName: 'cell_tower_triangulation.pdf', originalSource: 'Telecom provider', fileSize: 3_300_000, registeredAt: '2026-08-06T14:00:00', registeredBy: 'Insp. P. Singh', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00442', caseId: 'CASE-2026-010', sourceType: 'CCTV Recording', fileName: 'forecourt_camera_export.mp4', originalSource: 'Third-party CCTV', fileSize: 890_000_000, registeredAt: '2026-08-07T09:20:00', registeredBy: 'Insp. P. Singh', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00420', caseId: 'CASE-2026-009', sourceType: 'CCTV Recording', fileName: 'parking_dvr08_lvl2.mp4', originalSource: 'DVR-UNIT-08', fileSize: 3_100_000_000, registeredAt: '2026-07-30T11:00:00', registeredBy: 'Insp. R. Mehta', status: 'Flagged', sha256Status: 'Failed', md5Status: 'Warning' },
  { id: 'EVID-00421', caseId: 'CASE-2026-009', sourceType: 'Photograph', fileName: 'plate_match_reference.jpg', originalSource: 'Field capture', fileSize: 4_700_000, registeredAt: '2026-07-31T13:40:00', registeredBy: 'Insp. R. Mehta', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00422', caseId: 'CASE-2026-009', sourceType: 'Document', fileName: 'incident_correlation_notes.pdf', originalSource: 'Field report', fileSize: 900_000, registeredAt: '2026-08-01T10:20:00', registeredBy: 'Insp. R. Mehta', status: 'Active', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00390', caseId: 'CASE-2026-008', sourceType: 'CCTV Recording', fileName: 'storefront_camera_incident.mp4', originalSource: 'Third-party CCTV', fileSize: 420_000_000, registeredAt: '2026-07-12T15:40:00', registeredBy: 'Insp. A. Fernandes', status: 'Archived', sha256Status: 'Verified', md5Status: 'Verified' },
  { id: 'EVID-00360', caseId: 'CASE-2026-007', sourceType: 'Document', fileName: 'transaction_records_q2.xlsx', originalSource: 'Bank records', fileSize: 5_600_000, registeredAt: '2026-06-28T09:30:00', registeredBy: 'Insp. S. Kulkarni', status: 'Archived', sha256Status: 'Verified', md5Status: 'Verified' },
]

/**
 * A frontend-only, clearly-labeled SIMULATION of a blockchain evidence
 * anchor. No blockchain transaction of any kind is performed anywhere in
 * this codebase — this exists purely to visually represent the concept.
 */
function blockchainAnchorFor(seed: EvidenceSeed): BlockchainAnchor {
  const anyFailed = seed.sha256Status === 'Failed' || seed.md5Status === 'Failed'
  const bothVerified = seed.sha256Status === 'Verified' && seed.md5Status === 'Verified'
  const status = anyFailed ? 'Not Anchored' : bothVerified ? 'Demo Verified' : 'Pending Anchor'
  return {
    status,
    fingerprint: sha256For(seed.id),
    referenceId: `0x${seededHex(`${seed.id}:chain`, 40)}`,
    anchoredAt: status === 'Demo Verified' ? addMinutes(seed.registeredAt, 210) : null,
  }
}

const CUSTODY_STAGE_TEMPLATE: { stage: CustodyEvent['stage']; offsetMin: number; actor: 'registrant' | 'system'; action: string }[] = [
  { stage: 'Received', offsetMin: 0, actor: 'registrant', action: 'Evidence received into custody and logged' },
  { stage: 'Acquired', offsetMin: 4, actor: 'registrant', action: 'Source acquisition confirmed' },
  { stage: 'Hashed', offsetMin: 6, actor: 'system', action: 'SHA-256 / MD5 fingerprint generated' },
  { stage: 'Processed', offsetMin: 40, actor: 'system', action: 'Filesystem and container parsing completed' },
  { stage: 'Recovered', offsetMin: 75, actor: 'system', action: 'Recovery pass completed' },
  { stage: 'Analyzed', offsetMin: 130, actor: 'system', action: 'AI-assisted analysis completed (demo)' },
  { stage: 'Verified', offsetMin: 180, actor: 'registrant', action: 'Integrity re-verification performed' },
  { stage: 'Exported', offsetMin: 240, actor: 'registrant', action: 'Included in a generated forensic report' },
]

function custodyLogFor(seed: EvidenceSeed): CustodyEvent[] {
  return CUSTODY_STAGE_TEMPLATE.map(({ stage, offsetMin, actor, action }) => {
    let result: CustodyEvent['result'] = 'Success'
    if (stage === 'Verified' || stage === 'Hashed') {
      if (seed.sha256Status === 'Failed' || seed.md5Status === 'Failed') result = 'Failure'
      else if (seed.sha256Status === 'Warning' || seed.md5Status === 'Warning') result = 'Warning'
    }
    return {
      stage,
      timestamp: addMinutes(seed.registeredAt, offsetMin),
      actor: actor === 'registrant' ? seed.registeredBy : 'System (Automated)',
      action,
      result,
    }
  })
}

export const EVIDENCE: Evidence[] = EVIDENCE_SEEDS.map((seed) => ({
  id: seed.id,
  caseId: seed.caseId,
  sourceType: seed.sourceType,
  fileName: seed.fileName,
  originalSource: seed.originalSource,
  fileSize: seed.fileSize,
  sha256: sha256For(seed.id),
  md5: md5For(seed.id),
  sha256Status: seed.sha256Status,
  md5Status: seed.md5Status,
  registeredAt: seed.registeredAt,
  registeredBy: seed.registeredBy,
  status: seed.status,
  verificationHistory: verificationHistoryFor(seed.registeredAt, seed.sha256Status, seed.md5Status),
  blockchainAnchor: blockchainAnchorFor(seed),
  custodyLog: custodyLogFor(seed),
}))

// ---------------------------------------------------------------------------
// Recordings
// ---------------------------------------------------------------------------

/** India Standard Time is the assumed device-local zone for every source in this dataset. */
const IST_OFFSET_MIN = 330

function toNormalizedUTC(iso: string): string {
  const d = new Date(iso)
  d.setMinutes(d.getMinutes() - IST_OFFSET_MIN)
  return d.toISOString().slice(0, 19) + 'Z'
}

function reviewStatusFor(confidence: number, forceDismissed = false): ReviewStatus {
  if (forceDismissed) return 'Dismissed'
  return confidence >= 0.95 ? 'Confirmed' : 'Unreviewed'
}

const TIMESTAMP_META = {
  originalTimezone: 'IST (UTC+05:30)',
  timestampOffset: '+05:30',
  normalizationMethod: 'Device clock offset correction against NTP reference (demo)',
}

const VIDEO_AI_MODEL = { aiModel: 'YOLOv8 (Demo)', aiModelVersion: 'DEMO-1.0' }
const NO_AI_MODEL = { aiModel: 'N/A', aiModelVersion: 'N/A' }

interface RecordingSeed {
  id: string
  deviceId: string
  caseId: string
  cameraChannel: string
  durationSeconds: number
  resolution: string
  fps: number
  codec: string
  container: string
  recordingType: Recording['recordingType']
  extractionStatus: Recording['extractionStatus']
  fileSize: number
  recordedAt: string
  detectionEvents: DetectionEvent[]
}

const RECORDING_SEEDS: RecordingSeed[] = [
  {
    id: 'CAM-04-2026-08-21',
    deviceId: 'CAM-UNIT-04',
    caseId: 'CASE-2026-014',
    cameraChannel: 'CH-01',
    durationSeconds: 612,
    resolution: '1920x1080',
    fps: 30,
    codec: 'H.264',
    container: 'MP4 (ONVIF)',
    recordingType: 'Motion-Triggered',
    extractionStatus: 'Extracted',
    fileSize: 4_200_000_000,
    recordedAt: '2026-08-21T08:52:00',
    detectionEvents: [
      { timestampSeconds: 138, category: 'Person', label: 'Person detected', confidence: 0.984, reviewStatus: reviewStatusFor(0.984) },
      { timestampSeconds: 272, category: 'Vehicle', label: 'Vehicle detected', confidence: 0.972, reviewStatus: reviewStatusFor(0.972) },
      { timestampSeconds: 311, category: 'Anomaly', label: 'Abnormal movement detected', confidence: 0.871, reviewStatus: reviewStatusFor(0.871) },
      { timestampSeconds: 525, category: 'Object', label: 'License plate visible', confidence: 0.943, reviewStatus: reviewStatusFor(0.943) },
    ],
  },
  {
    id: 'NVR-07-2026-08-22',
    deviceId: 'NVR-UNIT-07',
    caseId: 'CASE-2026-014',
    cameraChannel: 'CH-02',
    durationSeconds: 480,
    resolution: '2560x1440',
    fps: 25,
    codec: 'H.264',
    container: 'DHAV',
    recordingType: 'Continuous',
    extractionStatus: 'Extracted',
    fileSize: 3_800_000_000,
    recordedAt: '2026-08-22T14:00:00',
    detectionEvents: [
      { timestampSeconds: 44, category: 'Vehicle', label: 'Vehicle detected', confidence: 0.961, reviewStatus: reviewStatusFor(0.961) },
      { timestampSeconds: 198, category: 'Motion', label: 'Motion detected near median', confidence: 0.902, reviewStatus: reviewStatusFor(0.902, true) },
    ],
  },
  {
    id: 'DVR-03-2026-08-21',
    deviceId: 'DVR-UNIT-03',
    caseId: 'CASE-2026-014',
    cameraChannel: 'CH-01',
    durationSeconds: 900,
    resolution: '1920x1080',
    fps: 25,
    codec: 'H.264',
    container: 'Proprietary (PS)',
    recordingType: 'Continuous',
    extractionStatus: 'Extracted',
    fileSize: 6_100_000_000,
    recordedAt: '2026-08-21T09:00:00',
    detectionEvents: [
      { timestampSeconds: 60, category: 'Vehicle', label: 'Multi-vehicle collision', confidence: 0.991, reviewStatus: reviewStatusFor(0.991) },
      { timestampSeconds: 96, category: 'Person', label: 'Person exits vehicle', confidence: 0.955, reviewStatus: reviewStatusFor(0.955) },
      { timestampSeconds: 340, category: 'Anomaly', label: 'Vehicle leaves scene', confidence: 0.933, reviewStatus: reviewStatusFor(0.933) },
    ],
  },
  {
    id: 'DVR-05-2026-08-14',
    deviceId: 'DVR-UNIT-05',
    caseId: 'CASE-2026-013',
    cameraChannel: 'CH-02',
    durationSeconds: 540,
    resolution: '1280x720',
    fps: 25,
    codec: 'H.264',
    container: 'Proprietary (PS)',
    recordingType: 'Continuous',
    extractionStatus: 'Extracted',
    fileSize: 1_900_000_000,
    recordedAt: '2026-08-14T22:10:00',
    detectionEvents: [
      { timestampSeconds: 88, category: 'Person', label: 'Person detected near loading bay', confidence: 0.947, reviewStatus: reviewStatusFor(0.947) },
      { timestampSeconds: 402, category: 'Anomaly', label: 'Unauthorized access point', confidence: 0.889, reviewStatus: reviewStatusFor(0.889) },
    ],
  },
  {
    id: 'DVR-05-2026-08-15',
    deviceId: 'DVR-UNIT-05',
    caseId: 'CASE-2026-013',
    cameraChannel: 'CH-02',
    durationSeconds: 396,
    resolution: '1280x720',
    fps: 25,
    codec: 'H.264',
    container: 'Proprietary (PS)',
    recordingType: 'Continuous',
    extractionStatus: 'Extracted',
    fileSize: 2_600_000_000,
    recordedAt: '2026-08-15T08:00:00',
    detectionEvents: [{ timestampSeconds: 55, category: 'Vehicle', label: 'Loading vehicle detected', confidence: 0.958, reviewStatus: reviewStatusFor(0.958) }],
  },
  {
    id: 'CAM-09-2026-08-10',
    deviceId: 'CAM-UNIT-09',
    caseId: 'CASE-2026-012',
    cameraChannel: 'CH-01',
    durationSeconds: 210,
    resolution: '2560x1440',
    fps: 30,
    codec: 'H.264',
    container: 'MP4 (ONVIF)',
    recordingType: 'Motion-Triggered',
    extractionStatus: 'Extracted',
    fileSize: 640_000_000,
    recordedAt: '2026-08-10T23:40:00',
    detectionEvents: [{ timestampSeconds: 42, category: 'Person', label: 'Person detected at entry', confidence: 0.938, reviewStatus: reviewStatusFor(0.938) }],
  },
  {
    id: 'CAM-09-2026-08-13',
    deviceId: 'CAM-UNIT-09',
    caseId: 'CASE-2026-012',
    cameraChannel: 'CH-01',
    durationSeconds: 180,
    resolution: '2560x1440',
    fps: 30,
    codec: 'H.264',
    container: 'MP4 (ONVIF)',
    recordingType: 'Motion-Triggered',
    extractionStatus: 'Extracted',
    fileSize: 580_000_000,
    recordedAt: '2026-08-13T19:10:00',
    detectionEvents: [{ timestampSeconds: 21, category: 'Motion', label: 'Motion detected', confidence: 0.881, reviewStatus: reviewStatusFor(0.881) }],
  },
  {
    id: 'STOR-02-2026-08-19',
    deviceId: 'STOR-UNIT-02',
    caseId: 'CASE-2026-011',
    cameraChannel: 'N/A',
    durationSeconds: 0,
    resolution: 'N/A',
    fps: 0,
    codec: 'N/A',
    container: 'Raw Disk Image',
    recordingType: 'Manual Export',
    extractionStatus: 'Extracted',
    fileSize: 512_000_000_000,
    recordedAt: '2026-08-19T15:12:00',
    detectionEvents: [],
  },
  {
    id: 'IMG-01-2026-08-06',
    deviceId: 'IMG-UNIT-01',
    caseId: 'CASE-2026-010',
    cameraChannel: 'N/A',
    durationSeconds: 0,
    resolution: 'N/A',
    fps: 0,
    codec: 'N/A',
    container: 'Logical Extraction (UFDR)',
    recordingType: 'Manual Export',
    extractionStatus: 'Extracted',
    fileSize: 118_000_000_000,
    recordedAt: '2026-08-06T10:10:00',
    detectionEvents: [],
  },
  {
    id: 'THIRD-PARTY-2026-08-07',
    deviceId: 'IMG-UNIT-01',
    caseId: 'CASE-2026-010',
    cameraChannel: 'CH-01',
    durationSeconds: 300,
    resolution: '1920x1080',
    fps: 25,
    codec: 'H.264',
    container: 'MP4',
    recordingType: 'Motion-Triggered',
    extractionStatus: 'Extracted',
    fileSize: 890_000_000,
    recordedAt: '2026-08-07T09:20:00',
    detectionEvents: [{ timestampSeconds: 130, category: 'Person', label: 'Individual matching description', confidence: 0.912, reviewStatus: reviewStatusFor(0.912) }],
  },
  {
    id: 'DVR-08-2026-07-30',
    deviceId: 'DVR-UNIT-08',
    caseId: 'CASE-2026-009',
    cameraChannel: 'CH-02',
    durationSeconds: 600,
    resolution: '1920x1080',
    fps: 25,
    codec: 'H.264',
    container: 'Proprietary (CP Plus)',
    recordingType: 'Continuous',
    extractionStatus: 'Partially Extracted',
    fileSize: 3_100_000_000,
    recordedAt: '2026-07-30T11:00:00',
    detectionEvents: [
      { timestampSeconds: 75, category: 'Vehicle', label: 'Vehicle detected', confidence: 0.905, reviewStatus: reviewStatusFor(0.905) },
      { timestampSeconds: 512, category: 'Anomaly', label: 'Vehicle re-identified from CASE-2026-009', confidence: 0.868, reviewStatus: reviewStatusFor(0.868) },
    ],
  },
  {
    id: 'DVR-03-2026-08-24',
    deviceId: 'DVR-UNIT-03',
    caseId: 'CASE-2026-014',
    cameraChannel: 'CH-03',
    durationSeconds: 420,
    resolution: '1920x1080',
    fps: 25,
    codec: 'H.264',
    container: 'Proprietary (PS)',
    recordingType: 'Continuous',
    extractionStatus: 'Extracted',
    fileSize: 2_900_000_000,
    recordedAt: '2026-08-24T07:30:00',
    detectionEvents: [{ timestampSeconds: 33, category: 'Vehicle', label: 'Vehicle detected', confidence: 0.947, reviewStatus: reviewStatusFor(0.947) }],
  },
  {
    id: 'NVR-07-2026-08-25',
    deviceId: 'NVR-UNIT-07',
    caseId: 'CASE-2026-014',
    cameraChannel: 'CH-05',
    durationSeconds: 360,
    resolution: '2560x1440',
    fps: 25,
    codec: 'H.264',
    container: 'DHAV',
    recordingType: 'Continuous',
    extractionStatus: 'Extracted',
    fileSize: 2_400_000_000,
    recordedAt: '2026-08-25T18:00:00',
    detectionEvents: [{ timestampSeconds: 210, category: 'Person', label: 'Person detected', confidence: 0.921, reviewStatus: reviewStatusFor(0.921) }],
  },
  {
    id: 'CAM-04-2026-08-26',
    deviceId: 'CAM-UNIT-04',
    caseId: 'CASE-2026-014',
    cameraChannel: 'CH-01',
    durationSeconds: 240,
    resolution: '1920x1080',
    fps: 30,
    codec: 'H.264',
    container: 'MP4 (ONVIF)',
    recordingType: 'Motion-Triggered',
    extractionStatus: 'Extracted',
    fileSize: 2_100_000_000,
    recordedAt: '2026-08-26T18:40:00',
    detectionEvents: [{ timestampSeconds: 18, category: 'Object', label: 'License plate visible', confidence: 0.958, reviewStatus: reviewStatusFor(0.958) }],
  },
  {
    id: 'MOB-01-2026-08-20',
    deviceId: 'MOB-UNIT-01',
    caseId: 'CASE-2026-011',
    cameraChannel: 'N/A',
    durationSeconds: 0,
    resolution: 'N/A',
    fps: 0,
    codec: 'N/A',
    container: 'Logical Extraction',
    recordingType: 'Manual Export',
    extractionStatus: 'Extracted',
    fileSize: 68_000_000_000,
    recordedAt: '2026-08-20T09:35:00',
    detectionEvents: [],
  },
  {
    id: 'CAM-09-2026-08-25',
    deviceId: 'CAM-UNIT-09',
    caseId: 'CASE-2026-012',
    cameraChannel: 'CH-01',
    durationSeconds: 150,
    resolution: '2560x1440',
    fps: 30,
    codec: 'H.264',
    container: 'MP4 (ONVIF)',
    recordingType: 'Motion-Triggered',
    extractionStatus: 'Extracted',
    fileSize: 410_000_000,
    recordedAt: '2026-08-25T20:15:00',
    detectionEvents: [{ timestampSeconds: 64, category: 'Person', label: 'Person detected', confidence: 0.902, reviewStatus: reviewStatusFor(0.902) }],
  },
  {
    id: 'DVR-05-2026-08-16',
    deviceId: 'DVR-UNIT-05',
    caseId: 'CASE-2026-013',
    cameraChannel: 'CH-04',
    durationSeconds: 300,
    resolution: '1280x720',
    fps: 25,
    codec: 'H.264',
    container: 'Proprietary (PS)',
    recordingType: 'Continuous',
    extractionStatus: 'Extracted',
    fileSize: 1_600_000_000,
    recordedAt: '2026-08-16T06:00:00',
    detectionEvents: [{ timestampSeconds: 12, category: 'Motion', label: 'Motion detected', confidence: 0.856, reviewStatus: reviewStatusFor(0.856) }],
  },
  {
    id: 'DVR-08-2026-08-05',
    deviceId: 'DVR-UNIT-08',
    caseId: 'CASE-2026-009',
    cameraChannel: 'CH-06',
    durationSeconds: 480,
    resolution: '1920x1080',
    fps: 25,
    codec: 'H.264',
    container: 'Proprietary (CP Plus)',
    recordingType: 'Continuous',
    extractionStatus: 'Partially Extracted',
    fileSize: 2_700_000_000,
    recordedAt: '2026-08-05T21:00:00',
    detectionEvents: [{ timestampSeconds: 91, category: 'Vehicle', label: 'Vehicle detected', confidence: 0.917, reviewStatus: reviewStatusFor(0.917) }],
  },
  {
    id: 'THIRD-PARTY-2026-07-12',
    deviceId: 'IMG-UNIT-01',
    caseId: 'CASE-2026-008',
    cameraChannel: 'CH-01',
    durationSeconds: 200,
    resolution: '1280x720',
    fps: 25,
    codec: 'H.264',
    container: 'MP4',
    recordingType: 'Motion-Triggered',
    extractionStatus: 'Extracted',
    fileSize: 420_000_000,
    recordedAt: '2026-07-12T15:40:00',
    detectionEvents: [{ timestampSeconds: 45, category: 'Person', label: 'Altercation detected', confidence: 0.895, reviewStatus: reviewStatusFor(0.895) }],
  },
  {
    id: 'NVR-10-2026-06-28',
    deviceId: 'NVR-UNIT-10',
    caseId: 'CASE-2026-007',
    cameraChannel: 'N/A',
    durationSeconds: 0,
    resolution: 'N/A',
    fps: 0,
    codec: 'N/A',
    container: 'Proprietary (Uniview)',
    recordingType: 'Manual Export',
    extractionStatus: 'Extracted',
    fileSize: 0,
    recordedAt: '2026-06-28T09:20:00',
    detectionEvents: [],
  },
]

export const RECORDINGS: Recording[] = RECORDING_SEEDS.map((seed) => ({
  ...seed,
  normalizedStartAt: toNormalizedUTC(seed.recordedAt),
  ...TIMESTAMP_META,
  ...(seed.durationSeconds > 0 ? VIDEO_AI_MODEL : NO_AI_MODEL),
}))

// ---------------------------------------------------------------------------
// Acquisition jobs & filesystem/format analysis
// ---------------------------------------------------------------------------

export const ACQUISITION_JOBS: AcquisitionJob[] = [
  {
    id: 'ACQ-00482',
    caseId: 'CASE-2026-014',
    evidenceId: 'EVID-00482',
    deviceId: 'DVR-UNIT-03',
    vendor: 'Hikvision',
    model: 'DS-7204HUHI-K1',
    firmware: 'V4.30.014',
    storageCapacity: 4_000_000_000_000,
    channelCount: 4,
    acquisitionMethod: 'Physical Image',
    status: 'Completed',
    progressPercent: 100,
    startedAt: '2026-08-21T09:12:00',
    completedAt: '2026-08-21T10:48:00',
    hashAlgorithm: 'SHA-256',
    hashResult: sha256For('EVID-00482'),
    warnings: [],
    filesystem: {
      detectedFormat: 'Hikvision HIKV proprietary volume',
      vendorStructure: 'HIKV cluster table (fixed 8MB cluster size)',
      parserUsed: 'Hikvision HIKV Parser v2.3 (demo)',
      parsingStatus: 'Success',
      partitions: [
        { name: 'System', sizeBytes: 512_000_000, type: 'HIKV-SYS', status: 'Recognized' },
        { name: 'Recording Region 0', sizeBytes: 2_000_000_000_000, type: 'HIKV-DATA', status: 'Recognized' },
        { name: 'Recording Region 1', sizeBytes: 1_940_000_000_000, type: 'HIKV-DATA', status: 'Recognized' },
      ],
      recognizedStructures: ['Cluster allocation table', 'Recording index (PIC/TIME table)', 'Channel metadata block'],
      unsupportedStructures: [],
      warnings: [],
    },
  },
  {
    id: 'ACQ-00483',
    caseId: 'CASE-2026-014',
    evidenceId: 'EVID-00483',
    deviceId: 'CAM-UNIT-04',
    vendor: 'Axis',
    model: 'P3245-LVE',
    firmware: '10.12.106',
    storageCapacity: 256_000_000_000,
    channelCount: 1,
    acquisitionMethod: 'Network Stream Capture',
    status: 'Completed',
    progressPercent: 100,
    startedAt: '2026-08-21T11:00:00',
    completedAt: '2026-08-21T11:14:00',
    hashAlgorithm: 'SHA-256',
    hashResult: sha256For('EVID-00483'),
    warnings: [],
    filesystem: {
      detectedFormat: 'ONVIF Profile G / edge SD card (exFAT)',
      vendorStructure: 'Axis edge-storage export manifest',
      parserUsed: 'Generic exFAT + ONVIF Manifest Parser v1.1 (demo)',
      parsingStatus: 'Success',
      partitions: [{ name: 'SD0', sizeBytes: 256_000_000_000, type: 'exFAT', status: 'Recognized' }],
      recognizedStructures: ['ONVIF recording manifest', 'MP4 container index'],
      unsupportedStructures: [],
      warnings: [],
    },
  },
  {
    id: 'ACQ-00484',
    caseId: 'CASE-2026-014',
    evidenceId: 'EVID-00484',
    deviceId: 'NVR-UNIT-07',
    vendor: 'Dahua',
    model: 'NVR4208-8P',
    firmware: 'V4.001.0000000.2',
    storageCapacity: 8_000_000_000_000,
    channelCount: 8,
    acquisitionMethod: 'Vendor SDK Export',
    status: 'Completed',
    progressPercent: 100,
    startedAt: '2026-08-22T14:00:00',
    completedAt: '2026-08-22T14:19:00',
    hashAlgorithm: 'SHA-256',
    hashResult: sha256For('EVID-00484'),
    warnings: ['Channel 06 export skipped — camera offline at capture time'],
    filesystem: {
      detectedFormat: 'Dahua DHAV proprietary container',
      vendorStructure: 'Dahua DH-NVR block table (variable cluster size)',
      parserUsed: 'Dahua DHAV Parser v1.8 (demo)',
      parsingStatus: 'Partial',
      partitions: [
        { name: 'Volume 1', sizeBytes: 4_000_000_000_000, type: 'DH-DATA', status: 'Recognized' },
        { name: 'Volume 2', sizeBytes: 4_000_000_000_000, type: 'DH-DATA', status: 'Partial' },
      ],
      recognizedStructures: ['DHAV frame index', 'Channel-to-camera mapping table'],
      unsupportedStructures: ['Dahua "smart event" metadata sidecar (undocumented binary layout)'],
      warnings: ['Vendor-specific event metadata could not be fully decoded — video and index data unaffected'],
    },
  },
  {
    id: 'ACQ-00471',
    caseId: 'CASE-2026-013',
    evidenceId: 'EVID-00471',
    deviceId: 'DVR-UNIT-05',
    vendor: 'Hikvision',
    model: 'DS-7208HQHI-K2',
    firmware: 'V4.02.024',
    storageCapacity: 2_000_000_000_000,
    channelCount: 8,
    acquisitionMethod: 'Physical Image',
    status: 'Warning',
    progressPercent: 100,
    startedAt: '2026-08-14T12:00:00',
    completedAt: '2026-08-14T13:42:00',
    hashAlgorithm: 'SHA-256',
    hashResult: sha256For('EVID-00471'),
    warnings: ['Hash re-verification returned a warning — see Integrity for details'],
    filesystem: {
      detectedFormat: 'Hikvision HIKV proprietary volume',
      vendorStructure: 'HIKV cluster table (fixed 8MB cluster size)',
      parserUsed: 'Hikvision HIKV Parser v2.3 (demo)',
      parsingStatus: 'Success',
      partitions: [{ name: 'Recording Region 0', sizeBytes: 2_000_000_000_000, type: 'HIKV-DATA', status: 'Recognized' }],
      recognizedStructures: ['Cluster allocation table', 'Recording index (PIC/TIME table)'],
      unsupportedStructures: [],
      warnings: [],
    },
  },
  {
    id: 'ACQ-00420',
    caseId: 'CASE-2026-009',
    evidenceId: 'EVID-00420',
    deviceId: 'DVR-UNIT-08',
    vendor: 'CP Plus',
    model: 'CP-UVR-0801E1',
    firmware: 'V2.8.3 build 210415',
    storageCapacity: 1_000_000_000_000,
    channelCount: 8,
    acquisitionMethod: 'Physical Image',
    status: 'Failed',
    progressPercent: 61,
    startedAt: '2026-07-30T10:40:00',
    completedAt: '2026-07-30T11:52:00',
    hashAlgorithm: 'SHA-256',
    hashResult: null,
    warnings: ['Disk read failure at sector offset ~61% — acquisition aborted', 'Partial image retained for recovery analysis'],
    filesystem: {
      detectedFormat: 'CP Plus proprietary volume (undocumented)',
      vendorStructure: 'Unknown — vendor does not publish a public specification',
      parserUsed: 'CP Plus Heuristic Parser v0.4 (demo, experimental)',
      parsingStatus: 'Failed',
      partitions: [
        { name: 'Region A', sizeBytes: 620_000_000_000, type: 'CPP-DATA?', status: 'Partial' },
        { name: 'Region B', sizeBytes: 380_000_000_000, type: 'Unknown', status: 'Unrecognized' },
      ],
      recognizedStructures: ['Approximate frame boundary markers (heuristic)'],
      unsupportedStructures: ['Recording index table', 'Channel metadata block', 'Timestamp encoding scheme'],
      warnings: [
        'No public filesystem specification exists for this vendor/firmware combination',
        'Bad sectors prevented full structural parsing — this is the core motivation for the Recovery workflow',
      ],
    },
  },
  {
    id: 'ACQ-00478',
    caseId: 'CASE-2026-011',
    evidenceId: 'EVID-00478',
    deviceId: 'STOR-UNIT-02',
    vendor: 'Seagate',
    model: 'Exos X18',
    firmware: 'SN04',
    storageCapacity: 18_000_000_000_000,
    channelCount: 0,
    acquisitionMethod: 'Physical Image',
    status: 'Completed',
    progressPercent: 100,
    startedAt: '2026-08-20T10:20:00',
    completedAt: '2026-08-20T14:05:00',
    hashAlgorithm: 'SHA-256',
    hashResult: sha256For('EVID-00478'),
    warnings: ['MD5 verified; SHA-256 flagged for manual re-check'],
    filesystem: {
      detectedFormat: 'NTFS',
      vendorStructure: 'Standard NTFS volume (no vendor-specific structure)',
      parserUsed: 'Generic NTFS Parser v3.0 (demo)',
      parsingStatus: 'Success',
      partitions: [{ name: 'Volume 1', sizeBytes: 18_000_000_000_000, type: 'NTFS', status: 'Recognized' }],
      recognizedStructures: ['MFT', 'Directory index', 'Journal ($LogFile)'],
      unsupportedStructures: [],
      warnings: [],
    },
  },
]

// ---------------------------------------------------------------------------
// Recovery reports
// ---------------------------------------------------------------------------

export const RECOVERY_REPORTS: RecoveryReport[] = [
  {
    id: 'REC-CASE-2026-014',
    caseId: 'CASE-2026-014',
    evidenceId: 'EVID-00482',
    deviceId: 'DVR-UNIT-03',
    totalRecordings: 428,
    recovered: 391,
    fragmented: 24,
    deleted: 13,
    damaged: 0,
    unrecoverable: 0,
    confidencePercent: 91.4,
    method: 'Cluster-chain reconstruction + recording index carving (demo)',
    limitations: [
      'Fragmented recordings may be missing frames at segment boundaries',
      'Recovered timestamps for carved (indexless) segments are estimated from adjacent index entries',
    ],
    items: [
      { id: 'REC-00342', cameraChannel: 'Camera 03', timeRangeStart: '2026-08-21T18:42:13', timeRangeEnd: '2026-08-21T18:46:51', status: 'Fragmented', confidence: 0.84, sourceLocation: 'Recording Region 0, cluster 0x1F2A00' },
      { id: 'REC-00343', cameraChannel: 'Camera 01', timeRangeStart: '2026-08-21T18:47:00', timeRangeEnd: '2026-08-21T19:02:11', status: 'Recovered', confidence: 0.99, sourceLocation: 'Recording Region 0, cluster 0x1F3100' },
      { id: 'REC-00344', cameraChannel: 'Camera 02', timeRangeStart: '2026-08-21T19:02:11', timeRangeEnd: '2026-08-21T19:18:40', status: 'Recovered', confidence: 0.98, sourceLocation: 'Recording Region 0, cluster 0x1F5C00' },
      { id: 'REC-00350', cameraChannel: 'Camera 04', timeRangeStart: '2026-08-21T20:10:00', timeRangeEnd: '2026-08-21T20:15:00', status: 'Deleted', confidence: 0.61, sourceLocation: 'Unallocated space, carved segment' },
    ],
  },
  {
    id: 'REC-CASE-2026-013',
    caseId: 'CASE-2026-013',
    evidenceId: 'EVID-00471',
    deviceId: 'DVR-UNIT-05',
    totalRecordings: 156,
    recovered: 132,
    fragmented: 18,
    deleted: 6,
    damaged: 0,
    unrecoverable: 0,
    confidencePercent: 88.7,
    method: 'Cluster-chain reconstruction (demo)',
    limitations: ['Overnight segments spanning the DST-adjacent window required manual timestamp cross-check'],
    items: [
      { id: 'REC-00201', cameraChannel: 'Camera 02', timeRangeStart: '2026-08-14T22:10:00', timeRangeEnd: '2026-08-14T22:19:00', status: 'Recovered', confidence: 0.96, sourceLocation: 'Recording Region 0, cluster 0x0A1200' },
      { id: 'REC-00214', cameraChannel: 'Camera 02', timeRangeStart: '2026-08-15T03:40:00', timeRangeEnd: '2026-08-15T03:52:00', status: 'Fragmented', confidence: 0.79, sourceLocation: 'Recording Region 0, cluster 0x0A4400' },
    ],
  },
  {
    id: 'REC-CASE-2026-009',
    caseId: 'CASE-2026-009',
    evidenceId: 'EVID-00420',
    deviceId: 'DVR-UNIT-08',
    totalRecordings: 96,
    recovered: 54,
    fragmented: 12,
    deleted: 8,
    damaged: 22,
    unrecoverable: 0,
    confidencePercent: 56.2,
    method: 'Heuristic frame-boundary carving (demo, experimental — no vendor index available)',
    limitations: [
      'Undocumented proprietary format prevented full index reconstruction',
      'Damaged sectors overlap the recording index region for Channels 05–08',
      'Recovery confidence is low relative to other cases in this dataset — do not treat as complete',
    ],
    items: [
      { id: 'REC-00088', cameraChannel: 'Camera 02', timeRangeStart: '2026-07-30T11:00:00', timeRangeEnd: '2026-07-30T11:10:00', status: 'Recovered', confidence: 0.72, sourceLocation: 'Region A, carved segment' },
      { id: 'REC-00091', cameraChannel: 'Camera 06', timeRangeStart: '2026-07-30T14:00:00', timeRangeEnd: '2026-07-30T14:00:00', status: 'Damaged', confidence: 0.11, sourceLocation: 'Region B, unreadable sectors' },
      { id: 'REC-00093', cameraChannel: 'Camera 07', timeRangeStart: '2026-07-30T15:20:00', timeRangeEnd: '2026-07-30T15:26:00', status: 'Unrecoverable', confidence: 0.0, sourceLocation: 'Region B, unreadable sectors' },
    ],
  },
  {
    id: 'REC-CASE-2026-012',
    caseId: 'CASE-2026-012',
    evidenceId: 'EVID-00455',
    deviceId: 'CAM-UNIT-09',
    totalRecordings: 64,
    recovered: 61,
    fragmented: 2,
    deleted: 1,
    damaged: 0,
    unrecoverable: 0,
    confidencePercent: 97.1,
    method: 'ONVIF manifest cross-check (demo)',
    limitations: ['Single deleted clip could only be partially time-bounded from adjacent manifest entries'],
    items: [
      { id: 'REC-00501', cameraChannel: 'Camera 01', timeRangeStart: '2026-08-10T23:40:00', timeRangeEnd: '2026-08-10T23:43:30', status: 'Recovered', confidence: 0.99, sourceLocation: 'SD0, MP4 container index' },
    ],
  },
]

// ---------------------------------------------------------------------------
// Cross-camera correlation
// ---------------------------------------------------------------------------

export const CORRELATION_EVENTS: CorrelationEvent[] = [
  {
    id: 'CORR-001',
    caseId: 'CASE-2026-014',
    title: 'Multi-vehicle collision sequence',
    description: 'Collision on DVR-UNIT-03 CH-01 is followed by a person exiting a vehicle, then the same vehicle is re-identified leaving the scene on NVR-UNIT-07 CH-05 four minutes later (normalized time).',
    normalizedTimestamp: '2026-08-21T03:31:00Z',
    cameraChannels: ['DVR-UNIT-03 / CH-01', 'NVR-UNIT-07 / CH-05'],
    recordings: ['DVR-03-2026-08-21', 'NVR-07-2026-08-25'],
    relatedEvidence: ['EVID-00482', 'EVID-00484'],
    confidence: 0.91,
  },
  {
    id: 'CORR-002',
    caseId: 'CASE-2026-014',
    title: 'Person exits vehicle, later appears on adjacent channel',
    description: 'A person detected exiting the vehicle on DVR-UNIT-03 CH-01 appears again on CAM-UNIT-04 CH-01 approximately six minutes later (normalized time), consistent with foot travel between the two camera fields of view.',
    normalizedTimestamp: '2026-08-21T03:26:36Z',
    cameraChannels: ['DVR-UNIT-03 / CH-01', 'CAM-UNIT-04 / CH-01'],
    recordings: ['DVR-03-2026-08-21', 'CAM-04-2026-08-21'],
    relatedEvidence: ['EVID-00482', 'EVID-00483'],
    confidence: 0.83,
  },
  {
    id: 'CORR-003',
    caseId: 'CASE-2026-014',
    title: 'License plate capture links to collision vehicle',
    description: 'A license plate captured on CAM-UNIT-04 CH-01 on a later date matches the vehicle description recorded during the collision sequence, suggesting the same vehicle returned to the area.',
    normalizedTimestamp: '2026-08-26T13:10:00Z',
    cameraChannels: ['CAM-UNIT-04 / CH-01'],
    recordings: ['CAM-04-2026-08-26'],
    relatedEvidence: ['EVID-00491', 'EVID-00482'],
    confidence: 0.76,
  },
]

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

export const VALIDATION_CHECKS: ValidationCheck[] = [
  {
    id: 'VAL-001',
    caseId: 'CASE-2026-014',
    category: 'Recovery Validation',
    expected: '428 recordings (source index)',
    actual: '391 recovered, 24 fragmented, 13 deleted',
    falsePositives: 0,
    falseNegatives: 13,
    accuracyPercent: 91.4,
    status: 'Warning',
    notes: 'All missing recordings accounted for by deletion or fragmentation — no recordings were silently lost.',
    groundTruthSource: 'DVR-UNIT-03 native recording index (pre-acquisition export)',
  },
  {
    id: 'VAL-002',
    caseId: 'CASE-2026-014',
    category: 'Parser Validation',
    expected: 'All HIKV cluster structures decoded',
    actual: 'Cluster allocation table and recording index fully decoded',
    falsePositives: 0,
    falseNegatives: 0,
    accuracyPercent: 100,
    status: 'Pass',
    notes: 'Hikvision HIKV format is well-documented in this simulated dataset.',
    groundTruthSource: 'Manufacturer format specification (demo reference)',
  },
  {
    id: 'VAL-003',
    caseId: 'CASE-2026-014',
    category: 'Timestamp Accuracy',
    expected: 'Device-reported IST timestamps normalized to UTC within ±1s',
    actual: 'All sampled timestamps normalized within tolerance',
    falsePositives: 0,
    falseNegatives: 0,
    accuracyPercent: 99.8,
    status: 'Pass',
    notes: 'Spot-checked against NTP reference log for the acquisition window.',
    groundTruthSource: 'Site NTP server log (demo reference)',
  },
  {
    id: 'VAL-004',
    caseId: 'CASE-2026-014',
    category: 'AI Detection Validation',
    expected: '4 ground-truth annotated events on CAM-04-2026-08-21',
    actual: '4 detected, 0 missed, 1 low-confidence anomaly flagged for review',
    falsePositives: 0,
    falseNegatives: 0,
    accuracyPercent: 96.5,
    status: 'Pass',
    notes: 'DEMO ANALYSIS — validated against manually annotated ground truth for this clip only, not a general model benchmark.',
    groundTruthSource: 'Manual frame-by-frame annotation (demo reference set)',
  },
  {
    id: 'VAL-005',
    caseId: 'CASE-2026-009',
    category: 'Recovery Validation',
    expected: '96 recordings (partial source index)',
    actual: '54 recovered, 12 fragmented, 8 deleted, 22 damaged/unreadable',
    falsePositives: 0,
    falseNegatives: 22,
    accuracyPercent: 56.2,
    status: 'Fail',
    notes: 'Undocumented CP Plus format and physical sector damage prevented acceptable recovery coverage — flagged for examiner review before reliance in court.',
    groundTruthSource: 'DVR-UNIT-08 partial recording index (recovered from damaged image)',
  },
  {
    id: 'VAL-006',
    caseId: 'CASE-2026-013',
    category: 'Parser Validation',
    expected: 'All HIKV cluster structures decoded',
    actual: 'Recording index decoded; one warning during hash re-verification',
    falsePositives: 0,
    falseNegatives: 0,
    accuracyPercent: 97.0,
    status: 'Warning',
    notes: 'Parsing succeeded; flagged for the associated integrity warning on EVID-00471, not a parser defect.',
    groundTruthSource: 'Manufacturer format specification (demo reference)',
  },
]

// ---------------------------------------------------------------------------
// Multi-vendor normalization
// ---------------------------------------------------------------------------

export const VENDOR_PROFILES: VendorProfile[] = [
  {
    vendor: 'Hikvision',
    adapter: 'Hikvision HIKV Adapter',
    supportLevel: 'Full',
    supportedModels: ['DS-7204HUHI-K1', 'DS-7208HQHI-K2', 'DS-2CD2043G2-I'],
    formatsSupported: ['HIKV proprietary volume', 'ONVIF Profile S/G export'],
    notes: 'Well-documented cluster/index structure; highest normalization confidence in this dataset.',
  },
  {
    vendor: 'Dahua',
    adapter: 'Dahua DHAV Adapter',
    supportLevel: 'Partial',
    supportedModels: ['NVR4208-8P'],
    formatsSupported: ['DHAV proprietary container'],
    notes: 'Core video and index structures normalize cleanly; vendor "smart event" metadata sidecar is not yet supported.',
  },
  {
    vendor: 'CP Plus',
    adapter: 'CP Plus Heuristic Adapter',
    supportLevel: 'Experimental',
    supportedModels: ['CP-UVR-0801E1'],
    formatsSupported: ['CP Plus proprietary volume (undocumented, heuristic parsing only)'],
    notes: 'No public specification is available for this vendor. Normalization relies on heuristic frame-boundary detection and cannot guarantee full structural recovery — this is the primary motivator for the Recovery workflow.',
  },
  {
    vendor: 'Uniview',
    adapter: 'Uniview ONVIF Adapter',
    supportLevel: 'Partial',
    supportedModels: ['NVR301-08S2'],
    formatsSupported: ['ONVIF Profile G export'],
    notes: 'Standard ONVIF export normalizes reliably; native proprietary export format is not yet mapped.',
  },
  {
    vendor: 'TP-Link',
    adapter: 'TP-Link Tapo Cloud Adapter',
    supportLevel: 'Experimental',
    supportedModels: ['Tapo C320WS', 'VIGI NVR1004H'],
    formatsSupported: ['Tapo cloud export (JSON manifest + MP4)'],
    notes: 'Adapter defined for architecture demonstration purposes — no unit of this vendor is present in the current case set.',
  },
  {
    vendor: 'Xiaomi',
    adapter: 'Xiaomi Mi Home Adapter',
    supportLevel: 'Experimental',
    supportedModels: ['Mi 360° Home Security Camera 2K'],
    formatsSupported: ['Mi Home local SD export (FAT32 + proprietary index)'],
    notes: 'Adapter defined for architecture demonstration purposes — no unit of this vendor is present in the current case set.',
  },
]

// ---------------------------------------------------------------------------
// Admin console (mock only — no real authorization)
// ---------------------------------------------------------------------------

export const SYSTEM_SERVICES: SystemService[] = [
  { name: 'API Gateway', status: 'Online', loadPercent: 34, failedJobsToday: 0 },
  { name: 'PostgreSQL (Primary)', status: 'Online', loadPercent: 51, failedJobsToday: 0 },
  { name: 'ML Inference Engine', status: 'Degraded', loadPercent: 88, failedJobsToday: 3 },
  { name: 'FFmpeg Extraction Worker', status: 'Online', loadPercent: 62, failedJobsToday: 1 },
  { name: 'Object Storage (Evidence Vault)', status: 'Online', loadPercent: 41, failedJobsToday: 0 },
  { name: 'Blockchain Anchor Service (Demo)', status: 'Online', loadPercent: 12, failedJobsToday: 0 },
]

export const ADMIN_USERS: AdminUser[] = [
  { id: 'A-0001', name: 'System Administrator', roleLabel: 'Administrator', clearance: 'L3', caseIds: [] },
  { id: 'I-1001', name: 'Insp. R. Mehta', roleLabel: 'Investigator', clearance: 'L2', caseIds: ['CASE-2026-014', 'CASE-2026-009'] },
  { id: 'I-1002', name: 'Insp. A. Fernandes', roleLabel: 'Investigator', clearance: 'L2', caseIds: ['CASE-2026-013', 'CASE-2026-008'] },
  { id: 'I-1003', name: 'Insp. S. Kulkarni', roleLabel: 'Investigator', clearance: 'L1', caseIds: ['CASE-2026-012', 'CASE-2026-007'] },
  { id: 'I-1004', name: 'Insp. N. Rao', roleLabel: 'Team Lead', clearance: 'L3', caseIds: ['CASE-2026-011'] },
  { id: 'I-1005', name: 'Insp. P. Singh', roleLabel: 'Director', clearance: 'L3', caseIds: ['CASE-2026-010'] },
]

export const SECURITY_EVENTS: SecurityEvent[] = [
  { id: 'SEC-001', timestamp: '2026-08-27T09:14:00', type: 'Access Denied', message: 'Attempted access to CASE-2026-014 evidence vault without clearance', severity: 'Warning', actor: 'I-1003' },
  { id: 'SEC-002', timestamp: '2026-08-25T22:03:00', type: 'Login Failure', message: '3 consecutive failed login attempts', severity: 'Warning', actor: 'unknown@10.0.4.18' },
  { id: 'SEC-003', timestamp: '2026-08-23T12:50:00', type: 'Integrity Alert', message: 'SHA-256 verification failed for EVID-00420', severity: 'Critical', actor: 'System (Automated)' },
  { id: 'SEC-004', timestamp: '2026-08-20T11:05:00', type: 'Unusual Activity', message: 'Bulk export of 6 evidence records outside business hours', severity: 'Warning', actor: 'I-1004' },
]

export const AI_SERVICE_STATUSES: AIServiceStatus[] = [
  { model: 'YOLOv8 (Demo)', version: 'DEMO-1.0', status: 'Online', queueLength: 2, processedToday: 47, failedJobs: 1 },
  { model: 'Face/Plate Recognition (Demo)', version: 'DEMO-0.9', status: 'Degraded', queueLength: 9, processedToday: 12, failedJobs: 3 },
]

// ---------------------------------------------------------------------------
// Activity log
// ---------------------------------------------------------------------------

export const ACTIVITY: ActivityEvent[] = [
  { id: 'ACT-030', timestamp: '2026-08-27T10:42:21', user: 'admin', action: 'VERIFIED HASH', resource: 'Evidence', resourceId: 'EVID-00482', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-029', timestamp: '2026-08-27T10:31:00', user: 'r.mehta', action: 'REGISTERED RECORDING', resource: 'Device', resourceId: 'DVR-UNIT-03', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-028', timestamp: '2026-08-27T10:12:00', user: 'system', action: 'AI ANOMALY DETECTED', resource: 'Recording', resourceId: 'CAM-04-2026-08-21', result: 'Warning', caseId: 'CASE-2026-014' },
  { id: 'ACT-027', timestamp: '2026-08-27T09:58:00', user: 'r.mehta', action: 'UPDATED CASE STATUS', resource: 'Case', resourceId: 'CASE-2026-014', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-026', timestamp: '2026-08-27T09:35:12', user: 'n.rao', action: 'STARTED VERIFICATION', resource: 'Evidence', resourceId: 'EVID-00478', result: 'Warning', caseId: 'CASE-2026-011' },
  { id: 'ACT-025', timestamp: '2026-08-27T08:15:44', user: 'n.rao', action: 'ACCESSED DEVICE', resource: 'Device', resourceId: 'MOB-UNIT-01', result: 'Success', caseId: 'CASE-2026-011' },
  { id: 'ACT-024', timestamp: '2026-08-27T08:02:10', user: 'system', action: 'DEVICE HEARTBEAT', resource: 'Device', resourceId: 'NVR-UNIT-07', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-023', timestamp: '2026-08-26T19:40:02', user: 'r.mehta', action: 'REGISTERED EVIDENCE', resource: 'Evidence', resourceId: 'EVID-00491', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-022', timestamp: '2026-08-26T18:40:00', user: 'r.mehta', action: 'REGISTERED RECORDING', resource: 'Device', resourceId: 'CAM-UNIT-04', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-021', timestamp: '2026-08-26T16:12:33', user: 'a.fernandes', action: 'GENERATED REPORT', resource: 'Report', resourceId: 'RPT-1042', result: 'Success', caseId: 'CASE-2026-013' },
  { id: 'ACT-020', timestamp: '2026-08-26T14:12:00', user: 's.kulkarni', action: 'UPDATED CASE', resource: 'Case', resourceId: 'CASE-2026-012', result: 'Success', caseId: 'CASE-2026-012' },
  { id: 'ACT-019', timestamp: '2026-08-25T20:15:40', user: 'system', action: 'AI DETECTION COMPLETE', resource: 'Recording', resourceId: 'CAM-09-2026-08-25', result: 'Success', caseId: 'CASE-2026-012' },
  { id: 'ACT-018', timestamp: '2026-08-25T18:00:00', user: 'r.mehta', action: 'REGISTERED RECORDING', resource: 'Device', resourceId: 'NVR-UNIT-07', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-017', timestamp: '2026-08-25T16:40:00', user: 'system', action: 'DEVICE OFFLINE', resource: 'Device', resourceId: 'DVR-UNIT-05', result: 'Failure', caseId: 'CASE-2026-013' },
  { id: 'ACT-016', timestamp: '2026-08-24T19:05:00', user: 'p.singh', action: 'UPDATED CASE STATUS', resource: 'Case', resourceId: 'CASE-2026-010', result: 'Success', caseId: 'CASE-2026-010' },
  { id: 'ACT-015', timestamp: '2026-08-24T07:30:00', user: 'r.mehta', action: 'REGISTERED RECORDING', resource: 'Device', resourceId: 'DVR-UNIT-03', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-014', timestamp: '2026-08-23T12:50:00', user: 'system', action: 'ACQUISITION ERROR', resource: 'Device', resourceId: 'DVR-UNIT-08', result: 'Failure', caseId: 'CASE-2026-009' },
  { id: 'ACT-013', timestamp: '2026-08-22T14:20:00', user: 'r.mehta', action: 'REGISTERED EVIDENCE', resource: 'Evidence', resourceId: 'EVID-00484', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-012', timestamp: '2026-08-21T11:05:00', user: 'r.mehta', action: 'REGISTERED EVIDENCE', resource: 'Evidence', resourceId: 'EVID-00483', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-011', timestamp: '2026-08-21T09:52:00', user: 'r.mehta', action: 'ACQUIRED RECORDING INDEX', resource: 'Device', resourceId: 'DVR-UNIT-03', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-010', timestamp: '2026-08-21T09:10:00', user: 'r.mehta', action: 'CREATED CASE', resource: 'Case', resourceId: 'CASE-2026-014', result: 'Success', caseId: 'CASE-2026-014' },
  { id: 'ACT-009', timestamp: '2026-08-20T11:00:00', user: 'n.rao', action: 'REGISTERED EVIDENCE', resource: 'Evidence', resourceId: 'EVID-00478', result: 'Warning', caseId: 'CASE-2026-011' },
  { id: 'ACT-008', timestamp: '2026-08-20T09:35:00', user: 'n.rao', action: 'COMPLETED EXTRACTION', resource: 'Device', resourceId: 'MOB-UNIT-01', result: 'Success', caseId: 'CASE-2026-011' },
  { id: 'ACT-007', timestamp: '2026-08-19T18:44:00', user: 'n.rao', action: 'VERIFIED HASH', resource: 'Evidence', resourceId: 'EVID-00475', result: 'Success', caseId: 'CASE-2026-011' },
  { id: 'ACT-006', timestamp: '2026-08-19T15:12:00', user: 'n.rao', action: 'ACQUIRED FORENSIC IMAGE', resource: 'Device', resourceId: 'STOR-UNIT-02', result: 'Success', caseId: 'CASE-2026-011' },
  { id: 'ACT-005', timestamp: '2026-08-16T06:00:00', user: 'system', action: 'MOTION DETECTED', resource: 'Recording', resourceId: 'DVR-05-2026-08-16', result: 'Success', caseId: 'CASE-2026-013' },
  { id: 'ACT-004', timestamp: '2026-08-15T08:20:00', user: 'a.fernandes', action: 'REGISTERED EVIDENCE', resource: 'Evidence', resourceId: 'EVID-00461', result: 'Success', caseId: 'CASE-2026-013' },
  { id: 'ACT-003', timestamp: '2026-08-14T13:00:00', user: 'a.fernandes', action: 'REGISTERED EVIDENCE', resource: 'Evidence', resourceId: 'EVID-00460', result: 'Success', caseId: 'CASE-2026-013' },
  { id: 'ACT-002', timestamp: '2026-08-14T12:15:00', user: 'a.fernandes', action: 'REGISTERED EVIDENCE', resource: 'Evidence', resourceId: 'EVID-00471', result: 'Warning', caseId: 'CASE-2026-013' },
  { id: 'ACT-001', timestamp: '2026-08-14T11:20:00', user: 'a.fernandes', action: 'CREATED CASE', resource: 'Case', resourceId: 'CASE-2026-013', result: 'Success', caseId: 'CASE-2026-013' },
]

// ---------------------------------------------------------------------------
// AI Insights
// ---------------------------------------------------------------------------

export const AI_INSIGHTS: AIInsight[] = [
  {
    id: 'INS-001',
    type: 'Suspicious Activity',
    title: 'Unusual vehicle movement',
    description: 'Unusual vehicle movement detected between 22:14 and 22:18, inconsistent with normal traffic flow patterns at this location.',
    confidence: 0.92,
    relatedEvidence: ['EVID-00483'],
    relatedRecordings: ['CAM-04-2026-08-21'],
    timestamp: '2026-08-27T10:12:00',
    caseId: 'CASE-2026-014',
  },
  {
    id: 'INS-002',
    type: 'Evidence Correlation',
    title: 'Recording correlated with device',
    description: 'Recording CAM-04 appears temporally correlated with device DVR-UNIT-03, suggesting both captured the same incident window.',
    confidence: 0.89,
    relatedEvidence: ['EVID-00482', 'EVID-00483'],
    relatedRecordings: ['CAM-04-2026-08-21', 'DVR-03-2026-08-21'],
    timestamp: '2026-08-27T10:05:00',
    caseId: 'CASE-2026-014',
  },
  {
    id: 'INS-003',
    type: 'Investigation Recommendation',
    title: 'Review flagged vehicle evidence',
    description: 'Review evidence EVID-00491 for potential connection to the detected vehicle identified in the highway incident recordings.',
    confidence: 0.85,
    relatedEvidence: ['EVID-00491'],
    relatedRecordings: ['CAM-04-2026-08-21'],
    timestamp: '2026-08-26T19:50:00',
    caseId: 'CASE-2026-014',
  },
  {
    id: 'INS-004',
    type: 'Suspicious Activity',
    title: 'Repeated access pattern detected',
    description: 'A repeated unauthorized access pattern was detected across two loading bay recordings, occurring at near-identical times on consecutive nights.',
    confidence: 0.88,
    relatedEvidence: ['EVID-00471', 'EVID-00461'],
    relatedRecordings: ['DVR-05-2026-08-14', 'DVR-05-2026-08-15'],
    timestamp: '2026-08-15T09:00:00',
    caseId: 'CASE-2026-013',
  },
  {
    id: 'INS-005',
    type: 'Evidence Correlation',
    title: 'Vehicle re-identified across cases',
    description: 'A vehicle detected in DVR-UNIT-08 footage shares visual characteristics with a vehicle logged in a separate incident within the same theft ring.',
    confidence: 0.81,
    relatedEvidence: ['EVID-00420', 'EVID-00421'],
    relatedRecordings: ['DVR-08-2026-07-30'],
    timestamp: '2026-08-01T11:00:00',
    caseId: 'CASE-2026-009',
  },
  {
    id: 'INS-006',
    type: 'Investigation Recommendation',
    title: 'Prioritize disk image re-verification',
    description: 'Evidence EVID-00478 returned a hash warning during automated verification. Recommend prioritizing manual re-verification before further analysis.',
    confidence: 0.94,
    relatedEvidence: ['EVID-00478'],
    relatedRecordings: [],
    timestamp: '2026-08-27T09:35:00',
    caseId: 'CASE-2026-011',
  },
]

// ---------------------------------------------------------------------------
// Integrity alerts
// ---------------------------------------------------------------------------

export const INTEGRITY_ALERTS: IntegrityAlert[] = [
  { id: 'ALERT-001', severity: 'Warning', message: 'Evidence EVID-00471 requires re-verification.', evidenceId: 'EVID-00471', timestamp: '2026-08-26T09:00:00' },
  { id: 'ALERT-002', severity: 'Warning', message: 'Evidence EVID-00478 returned an unexpected SHA-256 warning during scheduled verification.', evidenceId: 'EVID-00478', timestamp: '2026-08-27T09:35:00' },
  { id: 'ALERT-003', severity: 'Critical', message: 'Evidence EVID-00420 failed SHA-256 verification and requires immediate review.', evidenceId: 'EVID-00420', timestamp: '2026-08-01T08:00:00' },
]

// ---------------------------------------------------------------------------
// Timeline (consolidated forensic event history)
// ---------------------------------------------------------------------------

export const TIMELINE_EVENTS: TimelineEvent[] = [
  { id: 'TL-001', timestamp: '2026-08-21T09:10:00', category: 'Case Update', title: 'Case created', description: 'CASE-2026-014 opened following highway collision report.', caseId: 'CASE-2026-014', resourceId: 'CASE-2026-014' },
  { id: 'TL-002', timestamp: '2026-08-21T09:40:00', category: 'Device Discovered', title: 'Device registered', description: 'DVR-UNIT-03 registered to the investigation.', caseId: 'CASE-2026-014', resourceId: 'DVR-UNIT-03' },
  { id: 'TL-003', timestamp: '2026-08-21T09:30:00', category: 'Evidence Registered', title: 'Scene photograph registered', description: 'EVID-00485 registered from field capture.', caseId: 'CASE-2026-014', resourceId: 'EVID-00485' },
  { id: 'TL-004', timestamp: '2026-08-21T11:05:00', category: 'Evidence Registered', title: 'CCTV recording registered', description: 'EVID-00483 registered from CAM-UNIT-04.', caseId: 'CASE-2026-014', resourceId: 'EVID-00483' },
  { id: 'TL-005', timestamp: '2026-08-21T11:10:00', category: 'Hash Verified', title: 'Hash verification completed', description: 'SHA-256 and MD5 verified for EVID-00483.', caseId: 'CASE-2026-014', resourceId: 'EVID-00483' },
  { id: 'TL-006', timestamp: '2026-08-22T14:20:00', category: 'Recording Acquired', title: 'NVR channel export completed', description: 'EVID-00484 registered from NVR-UNIT-07.', caseId: 'CASE-2026-014', resourceId: 'EVID-00484' },
  { id: 'TL-007', timestamp: '2026-08-24T07:30:00', category: 'Recording Acquired', title: 'Additional DVR recording registered', description: 'New footage recorded from DVR-UNIT-03.', caseId: 'CASE-2026-014', resourceId: 'DVR-03-2026-08-24' },
  { id: 'TL-008', timestamp: '2026-08-25T18:00:00', category: 'Recording Acquired', title: 'NVR recording registered', description: 'Additional channel footage acquired from NVR-UNIT-07.', caseId: 'CASE-2026-014', resourceId: 'NVR-07-2026-08-25' },
  { id: 'TL-009', timestamp: '2026-08-26T18:40:00', category: 'Evidence Registered', title: 'License plate capture registered', description: 'EVID-00491 registered pending SHA-256 verification.', caseId: 'CASE-2026-014', resourceId: 'EVID-00491' },
  { id: 'TL-010', timestamp: '2026-08-27T10:05:00', category: 'AI Event Detected', title: 'Evidence correlation identified', description: 'AI analysis correlated CAM-04 recording with DVR-UNIT-03.', caseId: 'CASE-2026-014', resourceId: 'INS-002' },
  { id: 'TL-011', timestamp: '2026-08-27T10:12:00', category: 'AI Event Detected', title: 'Anomaly detected', description: 'Unusual vehicle movement flagged in CAM-04-2026-08-21.', caseId: 'CASE-2026-014', resourceId: 'CAM-04-2026-08-21' },
  { id: 'TL-012', timestamp: '2026-08-27T10:21:00', category: 'Hash Verified', title: 'Forensic image verified', description: 'SHA-256 and MD5 verified for EVID-00482.', caseId: 'CASE-2026-014', resourceId: 'EVID-00482' },
  { id: 'TL-013', timestamp: '2026-08-27T10:42:00', category: 'Analysis Completed', title: 'Verification cycle completed', description: 'Scheduled integrity verification completed for active evidence.', caseId: 'CASE-2026-014', resourceId: 'EVID-00482' },
  { id: 'TL-014', timestamp: '2026-08-14T11:20:00', category: 'Case Update', title: 'Case created', description: 'CASE-2026-013 opened following inventory loss report.', caseId: 'CASE-2026-013', resourceId: 'CASE-2026-013' },
  { id: 'TL-015', timestamp: '2026-08-14T12:15:00', category: 'Evidence Registered', title: 'Entry footage registered', description: 'EVID-00471 registered, later flagged for re-verification.', caseId: 'CASE-2026-013', resourceId: 'EVID-00471' },
  { id: 'TL-016', timestamp: '2026-08-15T09:00:00', category: 'AI Event Detected', title: 'Repeated access pattern flagged', description: 'AI analysis identified a recurring access pattern across two nights.', caseId: 'CASE-2026-013', resourceId: 'INS-004' },
  { id: 'TL-017', timestamp: '2026-08-25T16:40:00', category: 'Device Discovered', title: 'Device went offline', description: 'DVR-UNIT-05 stopped reporting heartbeat signals.', caseId: 'CASE-2026-013', resourceId: 'DVR-UNIT-05' },
  { id: 'TL-018', timestamp: '2026-08-19T09:10:00', category: 'Case Update', title: 'Case created', description: 'CASE-2026-011 opened following breach detection.', caseId: 'CASE-2026-011', resourceId: 'CASE-2026-011' },
  { id: 'TL-019', timestamp: '2026-08-19T15:12:00', category: 'Evidence Registered', title: 'Forensic disk image acquired', description: 'EVID-00475 acquired from STOR-UNIT-02.', caseId: 'CASE-2026-011', resourceId: 'EVID-00475' },
  { id: 'TL-020', timestamp: '2026-08-20T09:35:00', category: 'Recording Acquired', title: 'Mobile extraction completed', description: 'Full extraction completed from MOB-UNIT-01.', caseId: 'CASE-2026-011', resourceId: 'MOB-UNIT-01' },
  { id: 'TL-021', timestamp: '2026-08-27T09:35:00', category: 'AI Event Detected', title: 'Verification warning raised', description: 'EVID-00478 returned a SHA-256 warning during scheduled verification.', caseId: 'CASE-2026-011', resourceId: 'EVID-00478' },
]

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export const REPORTS: Report[] = [
  { id: 'RPT-1050', name: 'Highway Incident — Full Forensic Report', type: 'Full Forensic Report', caseId: 'CASE-2026-014', status: 'Ready', generatedAt: '2026-08-27T10:50:00', summary: 'Complete standardized forensic report for CASE-2026-014 — case information, evidence, acquisition, device identification, filesystem findings, recovery, timestamps, cross-camera correlation, AI findings, hashes, chain of custody, validation, and examiner details.' },
  { id: 'RPT-1048', name: 'Highway Incident — Case Summary', type: 'Case Summary', caseId: 'CASE-2026-014', status: 'Ready', generatedAt: '2026-08-27T09:00:00', summary: 'Consolidated overview of case status, evidence registration, and investigation progress for CASE-2026-014.' },
  { id: 'RPT-1047', name: 'Highway Incident — Evidence Integrity Report', type: 'Evidence Integrity', caseId: 'CASE-2026-014', status: 'Ready', generatedAt: '2026-08-27T09:05:00', summary: 'Hash verification results and chain-of-custody status for all registered evidence in CASE-2026-014.' },
  { id: 'RPT-1046', name: 'Highway Incident — Media Analysis Report', type: 'Media Analysis', caseId: 'CASE-2026-014', status: 'Generating', generatedAt: null, summary: 'AI detection summary and confidence scoring across all CCTV and DVR recordings in CASE-2026-014.' },
  { id: 'RPT-1045', name: 'Highway Incident — Timeline Report', type: 'Timeline', caseId: 'CASE-2026-014', status: 'Draft', generatedAt: null, summary: 'Chronological forensic event history for CASE-2026-014, from registration through analysis.' },
  { id: 'RPT-1042', name: 'Warehouse Theft — Case Summary', type: 'Case Summary', caseId: 'CASE-2026-013', status: 'Ready', generatedAt: '2026-08-26T16:12:00', summary: 'Consolidated overview of case status, evidence registration, and investigation progress for CASE-2026-013.' },
  { id: 'RPT-1041', name: 'Warehouse Theft — Evidence Integrity Report', type: 'Evidence Integrity', caseId: 'CASE-2026-013', status: 'Ready', generatedAt: '2026-08-25T10:00:00', summary: 'Hash verification results including the flagged EVID-00471 re-verification requirement.' },
  { id: 'RPT-1038', name: 'Corporate Data Breach — Case Summary', type: 'Case Summary', caseId: 'CASE-2026-011', status: 'Generating', generatedAt: null, summary: 'Consolidated overview of case status, evidence registration, and investigation progress for CASE-2026-011.' },
  { id: 'RPT-1030', name: 'Missing Person — Timeline Report', type: 'Timeline', caseId: 'CASE-2026-010', status: 'Ready', generatedAt: '2026-08-24T20:00:00', summary: 'Chronological forensic event history for CASE-2026-010.' },
  { id: 'RPT-1020', name: 'Vehicle Theft Ring — Media Analysis Report', type: 'Media Analysis', caseId: 'CASE-2026-009', status: 'Ready', generatedAt: '2026-08-23T13:30:00', summary: 'AI detection summary across parking structure recordings for CASE-2026-009.' },
  { id: 'RPT-1005', name: 'Assault Investigation — Case Summary', type: 'Case Summary', caseId: 'CASE-2026-008', status: 'Ready', generatedAt: '2026-08-01T09:30:00', summary: 'Final case summary report for closed investigation CASE-2026-008.' },
]
