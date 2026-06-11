package collector

import (
	"net"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/load"
	"github.com/shirou/gopsutil/v3/mem"
	psnet "github.com/shirou/gopsutil/v3/net"
	"github.com/shirou/gopsutil/v3/process"
	"github.com/avalab/edgehub-agent/internal/models"
)

func CollectSystemMetrics(agentMode string) *models.HeartbeatRequest {
	// 1. CPU — intervallo reale di 500ms per un delta affidabile
	cpuPercents, _ := cpu.Percent(500*time.Millisecond, false)
	cpuVal := 0.0
	if len(cpuPercents) > 0 {
		cpuVal = cpuPercents[0]
	}

	// 2. RAM
	vMem, _ := mem.VirtualMemory()
	memVal, memTotal, memAvail := 0.0, 0.0, 0.0
	var memUsedGB float64
	if vMem != nil {
		memVal = vMem.UsedPercent
		memTotal = float64(vMem.Total) / 1024 / 1024 / 1024
		memAvail = float64(vMem.Available) / 1024 / 1024 / 1024
		memUsedGB = float64(vMem.Used) / 1024 / 1024 / 1024
	}

	// 3. Swap — utile per capire se il sistema sta soffrendo di memory pressure
	swapTotal, swapUsed, swapUsedPct := 0.0, 0.0, 0.0
	swapMem, _ := mem.SwapMemory()
	if swapMem != nil {
		swapTotal = float64(swapMem.Total) / 1024 / 1024 / 1024
		swapUsed = float64(swapMem.Used) / 1024 / 1024 / 1024
		swapUsedPct = swapMem.UsedPercent
	}

	// 4. Disk (root)
	dUsage, _ := disk.Usage("/")
	diskVal, diskTotal, diskFree := 0.0, 0.0, 0.0
	var diskUsedGB float64
	if dUsage != nil {
		diskVal = dUsage.UsedPercent
		diskTotal = float64(dUsage.Total) / 1024 / 1024 / 1024
		diskFree = float64(dUsage.Free) / 1024 / 1024 / 1024
		diskUsedGB = float64(dUsage.Used) / 1024 / 1024 / 1024
	}

	// 5. Disk I/O — read/write bytes totali dall'avvio, utili per rilevare
	// thrashing o backup in corso che saturano il disco
	var diskReadBytes, diskWriteBytes uint64
	diskIO, _ := disk.IOCounters()
	for _, d := range diskIO {
		diskReadBytes += d.ReadBytes
		diskWriteBytes += d.WriteBytes
	}

	// 6. Host Info + Uptime
	hInfo, _ := host.Info()
	uptime := 0.0
	platform, platformVer, kernelVer, hostID := "unknown", "unknown", "unknown", "unknown"
	bootTime := uint64(0)
	if hInfo != nil {
		uptime = float64(hInfo.Uptime)
		platform = hInfo.Platform
		platformVer = hInfo.PlatformVersion
		kernelVer = hInfo.KernelVersion
		hostID = hInfo.HostID
		bootTime = hInfo.BootTime
	}

	// 7. CPU model + core count
	cpuModel := "unknown"
	cpuInfo, _ := cpu.Info()
	if len(cpuInfo) > 0 {
		cpuModel = cpuInfo[0].ModelName
	}
	cores, _ := cpu.Counts(true)
	physicalCores, _ := cpu.Counts(false)

	// 8. Load Average
	load1, load5, load15 := 0.0, 0.0, 0.0
	loadAvg, _ := load.Avg()
	if loadAvg != nil {
		load1 = loadAvg.Load1
		load5 = loadAvg.Load5
		load15 = loadAvg.Load15
	}

	// 9. Processi — totale e quanti in stato sleeping/running/zombie.
	// I processi zombie accumulati sono un segnale di problemi applicativi.
	pids, _ := process.Pids()
	processCount := len(pids)
	runningProcs, sleepingProcs, zombieProcs := 0, 0, 0
	for _, pid := range pids {
		p, err := process.NewProcess(pid)
		if err != nil {
			continue
		}
		status, err := p.Status()
		if err != nil {
			continue
		}
		switch status[0] {
		case "R":
			runningProcs++
		case "S", "I":
			sleepingProcs++
		case "Z":
			zombieProcs++
		}
	}

	// 10. Network I/O + connessioni TCP attive
	var bytesSent, bytesRecv, packetsSent, packetsRecv uint64
	var netErrIn, netErrOut uint64
	netIO, _ := psnet.IOCounters(false)
	if len(netIO) > 0 {
		bytesSent = netIO[0].BytesSent
		bytesRecv = netIO[0].BytesRecv
		packetsSent = netIO[0].PacketsSent
		packetsRecv = netIO[0].PacketsRecv
		netErrIn = netIO[0].Errin
		netErrOut = netIO[0].Errout
	}

	// ==========================================
    // 11. TEMPERATURE
    // ==========================================
    var maxTemp float64 = 0.0
    temperatures, err := host.SensorsTemperatures()
    if err == nil {
        for _, temp := range temperatures {
            if temp.Temperature > maxTemp && temp.Temperature < 200.0 {
                maxTemp = temp.Temperature
            }
        }
    }

	// Connessioni TCP stabilite — spike improvvisi segnalano DDoS o leak di connessioni
	tcpEstablished := 0
	conns, _ := psnet.Connections("tcp")
	for _, conn := range conns {
		if conn.Status == "ESTABLISHED" {
			tcpEstablished++
		}
	}

	extra := map[string]interface{}{
		// Identità
		"agent_mode":   agentMode,
		"host_id":      hostID,
		"boot_time":    bootTime, // timestamp unix: permette di rilevare riavvii inattesi

		// OS
		"os_platform":    platform,
		"os_version":     platformVer,
		"kernel_version": kernelVer,

		// CPU
		"cpu_model":         cpuModel,
		"cpu_cores_logical":  cores,
		"cpu_cores_physical": physicalCores,
		"cpu_temp_celsius":   maxTemp,

		// RAM
		"mem_total_gb":     memTotal,
		"mem_used_gb":      memUsedGB,
		"mem_available_gb": memAvail,

		// Swap — se swap_used_pct > 0 il nodo sta soffrendo
		"swap_total_gb":  swapTotal,
		"swap_used_gb":   swapUsed,
		"swap_used_pct":  swapUsedPct,

		// Disk
		"disk_total_gb": diskTotal,
		"disk_used_gb":  diskUsedGB,
		"disk_free_gb":  diskFree,

		// Disk I/O
		"disk_read_bytes":  diskReadBytes,
		"disk_write_bytes": diskWriteBytes,

		// Load
		"load_avg_1m":  load1,
		"load_avg_5m":  load5,
		"load_avg_15m": load15,

		// Processi
		"process_count":    processCount,
		"procs_running":    runningProcs,
		"procs_sleeping":   sleepingProcs,
		"procs_zombie":     zombieProcs, // > 0 è un warning applicativo

		// Network I/O
		"net_bytes_sent":   bytesSent,
		"net_bytes_recv":   bytesRecv,
		"net_packets_sent": packetsSent,
		"net_packets_recv": packetsRecv,
		"net_errors_in":    netErrIn,
		"net_errors_out":   netErrOut,

		// Connessioni TCP
		"tcp_established": tcpEstablished,
	}

	return &models.HeartbeatRequest{
		CPUUsage:      cpuVal,
		MemoryUsage:   memVal,
		DiskUsage:     diskVal,
		UptimeSeconds: uptime,
		IPAddress:     getLocalIP(),
		ExtraData:     extra,
	}
}

// getLocalIP legge le interfacce di rete locali invece di aprire
// una connessione verso 8.8.8.8 — funziona anche in reti air-gap.
func getLocalIP() string {
	ifaces, err := net.Interfaces()
	if err != nil {
		return "127.0.0.1"
	}
	for _, iface := range ifaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, addr := range addrs {
			var ip net.IP
			switch v := addr.(type) {
			case *net.IPNet:
				ip = v.IP
			case *net.IPAddr:
				ip = v.IP
			}
			if ip == nil || ip.IsLoopback() || ip.To4() == nil {
				continue
			}
			return ip.String()
		}
	}
	return "127.0.0.1"
}