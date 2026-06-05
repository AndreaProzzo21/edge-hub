package collector

import (
	"net"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/load"
	"github.com/shirou/gopsutil/v3/mem"
	psnet "github.com/shirou/gopsutil/v3/net" // Alias per non andare in conflitto col pacchetto "net" standard
	"github.com/shirou/gopsutil/v3/process"
	"github.com/avalab/edgehub-agent/internal/models"
)

// CollectSystemMetrics reads actual hardware data and builds the payload
func CollectSystemMetrics(agentMode string) *models.HeartbeatRequest {
	// 1. Read CPU
	cpuPercents, _ := cpu.Percent(0, false)
	cpuVal := 0.0
	if len(cpuPercents) > 0 {
		cpuVal = cpuPercents[0]
	}

	// 2. Read RAM
	vMem, _ := mem.VirtualMemory()
	memVal := 0.0
	if vMem != nil {
		memVal = vMem.UsedPercent
	}

	// 3. Read Disk (root partition)
	dUsage, _ := disk.Usage("/")
	diskVal := 0.0
	if dUsage != nil {
		diskVal = dUsage.UsedPercent
	}

	// 4. Read Uptime & Host Info
	hInfo, _ := host.Info()
	uptime := float64(0)
	platform := "unknown"
	platformVer := "unknown"
	if hInfo != nil {
		uptime = float64(hInfo.Uptime)
		platform = hInfo.Platform           // es. "ubuntu", "debian"
		platformVer = hInfo.PlatformVersion // es. "22.04"
	}

	// --- EXTRA TELEMETRY (Universale per ogni tipo di deploy) ---

	// A. CPU Cores (Logical)
	cores, _ := cpu.Counts(true)

	// B. System Load Average (1m, 5m, 15m)
	load1, load5, load15 := 0.0, 0.0, 0.0
	loadAvg, _ := load.Avg()
	if loadAvg != nil {
		load1 = loadAvg.Load1
		load5 = loadAvg.Load5
		load15 = loadAvg.Load15
	}

	// C. Active Processes count
	pids, _ := process.Pids()
	processCount := len(pids)

	// D. Network I/O (Total bytes sent/received)
	var bytesSent, bytesRecv uint64
	netIO, _ := psnet.IOCounters(false) // false = somma di tutte le interfacce di rete
	if len(netIO) > 0 {
		bytesSent = netIO[0].BytesSent
		bytesRecv = netIO[0].BytesRecv
	}

	// 5. Build Extra Data
	extra := map[string]interface{}{
		"agent_mode":     agentMode,
		"os_platform":    platform,
		"os_version":     platformVer,
		"cpu_cores":      cores,
		"process_count":  processCount,
		"load_avg_1m":    load1,
		"load_avg_5m":    load5,
		"load_avg_15m":   load15,
		"net_bytes_sent": bytesSent,
		"net_bytes_recv": bytesRecv,
	}

	// Payload matching exactly the FastAPI expectations
	return &models.HeartbeatRequest{
		CPUUsage:      cpuVal,
		MemoryUsage:   memVal,
		DiskUsage:     diskVal,
		UptimeSeconds: uptime,
		IPAddress:     getLocalIP(),
		ExtraData:     extra,
	}
}

// getLocalIP is a simple helper to find the active local IP address
func getLocalIP() string {
	conn, err := net.Dial("udp", "8.8.8.8:80")
	if err != nil {
		return "127.0.0.1"
	}
	defer conn.Close()

	localAddr := conn.LocalAddr().(*net.UDPAddr)
	return localAddr.IP.String()
}