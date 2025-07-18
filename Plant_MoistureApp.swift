import SwiftUI
import Foundation
import Network
import Combine

// MARK: - Data Models
struct PlantConfig: Codable {
    var dryThreshold: Double
    var wetThreshold: Double
    var updateInterval: Int
    var name: String
    var imagePath: String
    
    enum CodingKeys: String, CodingKey {
        case dryThreshold = "dry_threshold"
        case wetThreshold = "wet_threshold"
        case updateInterval = "update_interval"
        case name
        case imagePath = "image_path"
    }
}

struct PlantData: Identifiable {
    let id: Int
    var config: PlantConfig
    var voltage: Double
    var rawValue: Int
    var lastUpdate: Date
    var isConnected: Bool
    
    init(id: Int, config: PlantConfig) {
        self.id = id
        self.config = config
        self.voltage = 0.0
        self.rawValue = 0
        self.lastUpdate = Date()
        self.isConnected = false
    }
}

struct MoistureStatus {
    let statusText: String
    let statusColor: Color
    let progressValue: Double
    let showAlert: Bool
}

// MARK: - Network Manager
class NetworkManager: ObservableObject {
    @Published var plants: [PlantData] = []
    @Published var isConnected = false
    @Published var connectionStatus = "Disconnected"
    @Published var dryPlants: [String] = []
    
    private var connection: NWConnection?
    private var timer: Timer?
    private let serverHost: String
    private let serverPort: UInt16
    private let numPlants: Int
    
    init(serverHost: String = "172.20.10.2", serverPort: UInt16 = 5000, numPlants: Int = 40) {
        self.serverHost = serverHost
        self.serverPort = serverPort
        self.numPlants = numPlants
        
        // Initialize plants with default config
        for i in 0..<numPlants {
            let config = PlantConfig(
                dryThreshold: 1.5,
                wetThreshold: 2.5,
                updateInterval: 2,
                name: "Plant \(i + 1)",
                imagePath: ""
            )
            plants.append(PlantData(id: i, config: config))
        }
        
        startConnection()
    }
    
    private func startConnection() {
        let host = NWEndpoint.Host(serverHost)
        let port = NWEndpoint.Port(rawValue: serverPort)!
        
        connection = NWConnection(host: host, port: port, using: .tcp)
        
        connection?.stateUpdateHandler = { [weak self] state in
            DispatchQueue.main.async {
                switch state {
                case .ready:
                    self?.isConnected = true
                    self?.connectionStatus = "Connected"
                    self?.startDataRequest()
                case .failed(let error):
                    self?.isConnected = false
                    self?.connectionStatus = "Failed: \(error.localizedDescription)"
                    self?.scheduleReconnect()
                case .cancelled:
                    self?.isConnected = false
                    self?.connectionStatus = "Cancelled"
                default:
                    self?.isConnected = false
                    self?.connectionStatus = "Connecting..."
                }
            }
        }
        
        connection?.start(queue: .main)
    }
    
    private func startDataRequest() {
        // Start listening for incoming data immediately
        receiveData()
    }
    
    private func receiveData() {
        guard let connection = connection, connection.state == .ready else { return }
        
        connection.receive(minimumIncompleteLength: 1, maximumLength: 4096) { [weak self] data, _, isComplete, error in
            if let data = data, !data.isEmpty {
                self?.processReceivedData(data)
            }
            
            if let error = error {
                print("Receive error: \(error)")
                self?.scheduleReconnect()
                return
            }
            
            // Continue receiving data
            self?.receiveData()
        }
    }
    
    private func processReceivedData(_ data: Data) {
        guard let jsonString = String(data: data, encoding: .utf8) else { return }
        
        do {
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                DispatchQueue.main.async {
                    self.updatePlantsFromJSON(json)
                }
            }
        } catch {
            print("JSON parsing error: \(error)")
        }
    }
    
    private func updatePlantsFromJSON(_ json: [String: Any]) {
        var newDryPlants: [String] = []
        
        for i in 0..<numPlants {
            let plantKey = "plant_\(i)"
            if let voltage = json[plantKey] as? Double {
                plants[i].voltage = voltage
                plants[i].rawValue = Int(voltage * 1023 / 3.3)
                plants[i].lastUpdate = Date()
                plants[i].isConnected = true
                
                let status = getMoistureStatus(voltage: voltage, plantId: i)
                if status.showAlert {
                    newDryPlants.append(plants[i].config.name)
                }
            }
        }
        
        dryPlants = newDryPlants
    }
    
    private func scheduleReconnect() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) {
            self.startConnection()
        }
    }
    
    func getMoistureStatus(voltage: Double, plantId: Int) -> MoistureStatus {
        let plant = plants[plantId]
        let dryThreshold = plant.config.dryThreshold
        let wetThreshold = plant.config.wetThreshold
        let maxVoltage = 3.3
        
        let (statusText, statusColor, progressValue, showAlert): (String, Color, Double, Bool)
        
        if voltage < dryThreshold {
            statusText = "DRY - WATER NEEDED!"
            statusColor = Color.red.opacity(0.6)
            progressValue = dryThreshold > 0 ? (voltage / dryThreshold) * 20 : 0
            showAlert = true
        } else if voltage > wetThreshold {
            statusText = "TOO WET"
            statusColor = Color.blue.opacity(0.6)
            progressValue = 80 + ((voltage - wetThreshold) / (maxVoltage - wetThreshold)) * 20
            showAlert = false
        } else {
            statusText = "PERFECT"
            statusColor = Color.green.opacity(0.6)
            progressValue = 20 + ((voltage - dryThreshold) / (wetThreshold - dryThreshold)) * 60
            showAlert = false
        }
        
        return MoistureStatus(
            statusText: statusText,
            statusColor: statusColor,
            progressValue: max(0, min(100, progressValue)),
            showAlert: showAlert
        )
    }
    
    func updatePlantName(_ plantId: Int, name: String) {
        plants[plantId].config.name = name
        // Here you would typically save to UserDefaults or send to server
    }
    
    func updatePlantThresholds(_ plantId: Int, dryThreshold: Double, wetThreshold: Double) {
        plants[plantId].config.dryThreshold = dryThreshold
        plants[plantId].config.wetThreshold = wetThreshold
        // Here you would typically save to UserDefaults or send to server
    }
    
    deinit {
        timer?.invalidate()
        connection?.cancel()
    }
}

//// MARK: - Main App View
//struct ContentView: View {
//    @StateObject private var networkManager = NetworkManager()
//    @State private var showingSettings = false
//    
//    var body: some View {
//        NavigationView {
//            HStack(spacing: 0) {
//                // Main plant grid
//                ScrollView {
//                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 3), spacing: 10) {
//                        ForEach(networkManager.plants) { plant in
//                            PlantTileView(plant: plant, networkManager: networkManager)
//                        }
//                    }
//                    .padding()
//                }
//                
//                // Dry plants sidebar
//                VStack {
//                    Text("Dry Plants")
//                        .font(.headline)
//                        .fontWeight(.bold)
//                        .foregroundColor(.white)
//                        .padding()
//                    
//                    List(networkManager.dryPlants, id: \.self) { plantName in
//                        Text(plantName)
//                            .font(.system(size: 12))
//                            .foregroundColor(.red)
//                            .fontWeight(.bold)
//                    }
//                    .background(Color.white)
//                    .cornerRadius(8)
//                    .padding(.horizontal)
//                    
//                    Spacer()
//                }
//                .frame(width: 150)
//                .background(Color(red: 0.18, green: 0.55, blue: 0.34))
//            }
//            .navigationTitle("Plant Moisture Monitor")
//            .navigationBarTitleDisplayMode(.inline)
//            .toolbar {
//                ToolbarItem(placement: .navigationBarTrailing) {
//                    Button("Settings") {
//                        showingSettings = true
//                    }
//                }
//                ToolbarItem(placement: .navigationBarLeading) {
//                    HStack {
//                        Circle()
//                            .fill(networkManager.isConnected ? Color.green : Color.red)
//                            .frame(width: 10, height: 10)
//                        Text(networkManager.connectionStatus)
//                            .font(.caption)
//                    }
//                }
//            }
//            .sheet(isPresented: $showingSettings) {
//                SettingsView(networkManager: networkManager)
//            }
//        }
//        .background(Color(red: 0.18, green: 0.55, blue: 0.34))
//    }
//}
//
//// MARK: - Plant Tile View
//struct PlantTileView: View {
//    let plant: PlantData
//    @ObservedObject var networkManager: NetworkManager
//    @State private var showingDetails = false
//    @State private var showingThresholds = false
//    @State private var editingName = false
//    @State private var plantName: String
//    
//    init(plant: PlantData, networkManager: NetworkManager) {
//        self.plant = plant
//        self.networkManager = networkManager
//        self._plantName = State(initialValue: plant.config.name)
//    }
//    
//    var moistureStatus: MoistureStatus {
//        networkManager.getMoistureStatus(voltage: plant.voltage, plantId: plant.id)
//    }
//    
//    var body: some View {
//        VStack(spacing: 5) {
//            // Name and alert
//            HStack {
//                if editingName {
//                    TextField("Plant Name", text: $plantName)
//                        .textFieldStyle(RoundedBorderTextFieldStyle())
//                        .font(.system(size: 12))
//                        .onSubmit {
//                            networkManager.updatePlantName(plant.id, name: plantName)
//                            editingName = false
//                        }
//                } else {
//                    Text(plant.config.name)
//                        .font(.system(size: 12, weight: .bold))
//                        .onTapGesture {
//                            editingName = true
//                        }
//                }
//                
//                Spacer()
//                
//                if moistureStatus.showAlert {
//                    Text("!")
//                        .font(.system(size: 12, weight: .bold))
//                        .foregroundColor(.red)
//                }
//            }
//            .padding(.horizontal, 8)
//            
//            // Plant image placeholder
//            RoundedRectangle(cornerRadius: 8)
//                .fill(Color.gray.opacity(0.3))
//                .frame(width: 40, height: 40)
//                .overlay(
//                    Text("🌱")
//                        .font(.system(size: 20))
//                )
//            
//            // Status
//            Text(moistureStatus.statusText)
//                .font(.system(size: 10, weight: .bold))
//                .foregroundColor(.black)
//                .multilineTextAlignment(.center)
//                .frame(height: 30)
//            
//            // Voltage
//            Text("Voltage: \(String(format: "%.2f", plant.voltage)) V")
//                .font(.system(size: 8))
//                .foregroundColor(.black)
//            
//            // Progress bar
//            ProgressView(value: moistureStatus.progressValue, total: 100)
//                .scaleEffect(x: 1, y: 0.8)
//                .padding(.horizontal, 8)
//            
//            // Buttons
//            HStack(spacing: 4) {
//                Button("Thresholds") {
//                    showingThresholds = true
//                }
//                .buttonStyle(CompactButtonStyle(color: .green))
//                
//                Button("Details") {
//                    showingDetails = true
//                }
//                .buttonStyle(CompactButtonStyle(color: .blue))
//            }
//            .padding(.horizontal, 8)
//        }
//        .padding(8)
//        .background(moistureStatus.statusColor)
//        .cornerRadius(10)
//        .frame(width: 120, height: 180)
//        .sheet(isPresented: $showingDetails) {
//            PlantDetailsView(plant: plant, networkManager: networkManager)
//        }
//        .sheet(isPresented: $showingThresholds) {
//            ThresholdsView(plant: plant, networkManager: networkManager)
//        }
//    }
//}
//
//// MARK: - Compact Button Style
//struct CompactButtonStyle: ButtonStyle {
//    let color: Color
//    
//    func makeBody(configuration: Configuration) -> some View {
//        configuration.label
//            .font(.system(size: 7, weight: .bold))
//            .foregroundColor(.white)
//            .padding(.horizontal, 6)
//            .padding(.vertical, 2)
//            .background(color)
//            .cornerRadius(4)
//            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
//    }
//}
//
// MARK: - Plant Details View
struct PlantDetailsView: View {
    let plant: PlantData
    @ObservedObject var networkManager: NetworkManager
    @Environment(\.dismiss) private var dismiss
    
    var moistureStatus: MoistureStatus {
        networkManager.getMoistureStatus(voltage: plant.voltage, plantId: plant.id)
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Text(plant.config.name)
                    .font(.title)
                    .fontWeight(.bold)
                
                // Large plant image placeholder
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 120, height: 120)
                    .overlay(
                        Text("🌱")
                            .font(.system(size: 60))
                    )
                
                VStack(alignment: .leading, spacing: 10) {
                    Text("Status: \(moistureStatus.statusText)")
                        .font(.system(size: 16))
                    
                    Text("Voltage: \(String(format: "%.2f", plant.voltage)) V")
                        .font(.system(size: 16))
                    
                    Text("Dry Threshold: \(String(format: "%.2f", plant.config.dryThreshold)) V")
                        .font(.system(size: 16))
                    
                    Text("Wet Threshold: \(String(format: "%.2f", plant.config.wetThreshold)) V")
                        .font(.system(size: 16))
                    
                    Text("Last Update: \(plant.lastUpdate.formatted(.dateTime.hour().minute().second()))")
                        .font(.system(size: 16))
                        .foregroundColor(.gray)
                }
                .padding()
                .background(Color.gray.opacity(0.1))
                .cornerRadius(12)
                
                Spacer()
            }
            .padding()
            .navigationTitle("Plant Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

// MARK: - Thresholds View
struct ThresholdsView: View {
    let plant: PlantData
    @ObservedObject var networkManager: NetworkManager
    @Environment(\.dismiss) private var dismiss
    
    @State private var dryThreshold: String
    @State private var wetThreshold: String
    @State private var showingError = false
    @State private var errorMessage = ""
    
    init(plant: PlantData, networkManager: NetworkManager) {
        self.plant = plant
        self.networkManager = networkManager
        self._dryThreshold = State(initialValue: String(format: "%.2f", plant.config.dryThreshold))
        self._wetThreshold = State(initialValue: String(format: "%.2f", plant.config.wetThreshold))
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Text("Set Thresholds for \(plant.config.name)")
                    .font(.title2)
                    .fontWeight(.bold)
                    .multilineTextAlignment(.center)
                
                VStack(alignment: .leading, spacing: 15) {
                    VStack(alignment: .leading) {
                        Text("Dry Threshold (V):")
                            .font(.system(size: 16))
                        TextField("0.00", text: $dryThreshold)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .keyboardType(.decimalPad)
                    }
                    
                    VStack(alignment: .leading) {
                        Text("Wet Threshold (V):")
                            .font(.system(size: 16))
                        TextField("0.00", text: $wetThreshold)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .keyboardType(.decimalPad)
                    }
                }
                .padding()
                
                Button("Save") {
                    saveThresholds()
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                
                if showingError {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.caption)
                }
                
                Spacer()
            }
            .padding()
            .navigationTitle("Thresholds")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
    
    private func saveThresholds() {
        guard let dry = Double(dryThreshold),
              let wet = Double(wetThreshold) else {
            showError("Enter valid numbers")
            return
        }
        
        guard dry >= 0.0 && dry <= 3.3 && wet >= 0.0 && wet <= 3.3 && dry < wet else {
            showError("Invalid values (0.0-3.3, dry < wet)")
            return
        }
        
        networkManager.updatePlantThresholds(plant.id, dryThreshold: dry, wetThreshold: wet)
        dismiss()
    }
    
    private func showError(_ message: String) {
        errorMessage = message
        showingError = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            showingError = false
        }
    }
}

// MARK: - Settings View
struct SettingsView: View {
    @ObservedObject var networkManager: NetworkManager
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                Text("Settings")
                    .font(.title)
                    .fontWeight(.bold)
                
                VStack(alignment: .leading, spacing: 15) {
                    Text("Connection Status: \(networkManager.connectionStatus)")
                        .font(.system(size: 16))
                    
                    Text("Total Plants: \(networkManager.plants.count)")
                        .font(.system(size: 16))
                    
                    Text("Dry Plants: \(networkManager.dryPlants.count)")
                        .font(.system(size: 16))
                        .foregroundColor(.red)
                }
                .padding()
                .background(Color.gray.opacity(0.1))
                .cornerRadius(12)
                
                Spacer()
            }
            .padding()
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

// MARK: - App Entry Point
@main
struct PlantMonitorApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

//import SwiftUI
//import Foundation
//import Network
//import Combine
//
//// MARK: - Data Models
//struct PlantConfig: Codable {
//    var dryThreshold: Double
//    var wetThreshold: Double
//    var updateInterval: Int
//    var name: String
//    var imagePath: String
//    
//    enum CodingKeys: String, CodingKey {
//        case dryThreshold = "dry_threshold"
//        case wetThreshold = "wet_threshold"
//        case updateInterval = "update_interval"
//        case name
//        case imagePath = "image_path"
//    }
//}
//
//struct PlantData: Identifiable {
//    let id: Int
//    var config: PlantConfig
//    var voltage: Double
//    var rawValue: Int
//    var lastUpdate: Date
//    var isConnected: Bool
//    
//    init(id: Int, config: PlantConfig) {
//        self.id = id
//        self.config = config
//        self.voltage = 0.0
//        self.rawValue = 0
//        self.lastUpdate = Date()
//        self.isConnected = false
//    }
//}
//
//struct MoistureStatus {
//    let statusText: String
//    let statusColor: Color
//    let progressValue: Double
//    let showAlert: Bool
//}
//
//// MARK: - Network Manager
//class NetworkManager: ObservableObject {
//    @Published var plants: [PlantData] = []
//    @Published var isConnected = false
//    @Published var connectionStatus = "Disconnected"
//    @Published var dryPlants: [String] = []
//    
//    private var connection: NWConnection?
//    private var timer: Timer?
//    private let serverHost: String
//    private let serverPort: UInt16
//    private let numPlants: Int
//    
//    init(serverHost: String = "172.20.10.2", serverPort: UInt16 = 5000, numPlants: Int = 40) {
//        self.serverHost = serverHost
//        self.serverPort = serverPort
//        self.numPlants = numPlants
//        
//        // Initialize plants with default config
//        for i in 0..<numPlants {
//            let config = PlantConfig(
//                dryThreshold: 1.5,
//                wetThreshold: 2.5,
//                updateInterval: 2,
//                name: "Plant \(i + 1)",
//                imagePath: ""
//            )
//            plants.append(PlantData(id: i, config: config))
//        }
//        
//        startConnection()
//    }
//    
//    private func startConnection() {
//        let host = NWEndpoint.Host(serverHost)
//        let port = NWEndpoint.Port(rawValue: serverPort)!
//        
//        connection = NWConnection(host: host, port: port, using: .tcp)
//        
//        connection?.stateUpdateHandler = { [weak self] state in
//            DispatchQueue.main.async {
//                switch state {
//                case .ready:
//                    self?.isConnected = true
//                    self?.connectionStatus = "Connected"
//                    self?.startDataRequest()
//                case .failed(let error):
//                    self?.isConnected = false
//                    self?.connectionStatus = "Failed: \(error.localizedDescription)"
//                    self?.scheduleReconnect()
//                case .cancelled:
//                    self?.isConnected = false
//                    self?.connectionStatus = "Cancelled"
//                default:
//                    self?.isConnected = false
//                    self?.connectionStatus = "Connecting..."
//                }
//            }
//        }
//        
//        connection?.start(queue: .main)
//    }
//    
//    private func startDataRequest() {
//        timer?.invalidate()
//        timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
//            self?.requestData()
//        }
//    }
//    
//    private func requestData() {
//        guard let connection = connection, connection.state == .ready else { return }
//        
//        let request = "GET_DATA\n"
//        connection.send(content: request.data(using: .utf8), completion: .contentProcessed({ [weak self] error in
//            if let error = error {
//                print("Send error: \(error)")
//                return
//            }
//            
//            connection.receive(minimumIncompleteLength: 1, maximumLength: 4096) { [weak self] data, _, isComplete, error in
//                if let data = data, !data.isEmpty {
//                    self?.processReceivedData(data)
//                }
//                
//                if let error = error {
//                    print("Receive error: \(error)")
//                }
//            }
//        }))
//    }
//    
//    private func processReceivedData(_ data: Data) {
//        guard let jsonString = String(data: data, encoding: .utf8) else { return }
//        
//        do {
//            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
//                DispatchQueue.main.async {
//                    self.updatePlantsFromJSON(json)
//                }
//            }
//        } catch {
//            print("JSON parsing error: \(error)")
//        }
//    }
//    
//    private func updatePlantsFromJSON(_ json: [String: Any]) {
//        var newDryPlants: [String] = []
//        
//        for i in 0..<numPlants {
//            let plantKey = "plant_\(i)"
//            if let voltage = json[plantKey] as? Double {
//                plants[i].voltage = voltage
//                plants[i].rawValue = Int(voltage * 1023 / 3.3)
//                plants[i].lastUpdate = Date()
//                plants[i].isConnected = true
//                
//                let status = getMoistureStatus(voltage: voltage, plantId: i)
//                if status.showAlert {
//                    newDryPlants.append(plants[i].config.name)
//                }
//            }
//        }
//        
//        dryPlants = newDryPlants
//    }
//    
//    private func scheduleReconnect() {
//        DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) {
//            self.startConnection()
//        }
//    }
//    
//    func getMoistureStatus(voltage: Double, plantId: Int) -> MoistureStatus {
//        let plant = plants[plantId]
//        let dryThreshold = plant.config.dryThreshold
//        let wetThreshold = plant.config.wetThreshold
//        let maxVoltage = 3.3
//        
//        let (statusText, statusColor, progressValue, showAlert): (String, Color, Double, Bool)
//        
//        if voltage < dryThreshold {
//            statusText = "DRY - WATER NEEDED!"
//            statusColor = Color.red.opacity(0.6)
//            progressValue = dryThreshold > 0 ? (voltage / dryThreshold) * 20 : 0
//            showAlert = true
//        } else if voltage > wetThreshold {
//            statusText = "TOO WET"
//            statusColor = Color.blue.opacity(0.6)
//            progressValue = 80 + ((voltage - wetThreshold) / (maxVoltage - wetThreshold)) * 20
//            showAlert = false
//        } else {
//            statusText = "PERFECT"
//            statusColor = Color.green.opacity(0.6)
//            progressValue = 20 + ((voltage - dryThreshold) / (wetThreshold - dryThreshold)) * 60
//            showAlert = false
//        }
//        
//        return MoistureStatus(
//            statusText: statusText,
//            statusColor: statusColor,
//            progressValue: max(0, min(100, progressValue)),
//            showAlert: showAlert
//        )
//    }
//    
//    func updatePlantName(_ plantId: Int, name: String) {
//        plants[plantId].config.name = name
//        // Here you would typically save to UserDefaults or send to server
//    }
//    
//    func updatePlantThresholds(_ plantId: Int, dryThreshold: Double, wetThreshold: Double) {
//        plants[plantId].config.dryThreshold = dryThreshold
//        plants[plantId].config.wetThreshold = wetThreshold
//        // Here you would typically save to UserDefaults or send to server
//    }
//    
//    deinit {
//        timer?.invalidate()
//        connection?.cancel()
//    }
//}
//
// MARK: - Main App View
struct ContentView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var showingSettings = false
    
    var body: some View {
        NavigationView {
            HStack(spacing: 0) {
                // Main plant grid
                ScrollView {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 2), spacing: 10) {
                        ForEach(networkManager.plants) { plant in
                            PlantTileView(plant: plant, networkManager: networkManager)
                        }
                    }
                    .padding()
                }
                .frame(maxWidth: .infinity) // Allow grid to expand to available space
                
                // Spacer to push dry plants to the right
                Spacer()
                
                // Dry plants sidebar
                VStack {
                    Text("Dry Plants")
                        .font(.headline)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                        .padding()
                    
                    List(networkManager.dryPlants, id: \.self) { plantName in
                        Text(plantName)
                            .font(.system(size: 12))
                            .foregroundColor(.red)
                            .fontWeight(.bold)
                    }
                    .background(Color.white)
                    .cornerRadius(8)
                    .padding(.horizontal)
                    
                    Spacer()
                }

                .frame(width: 150, height: 775)
                .background(Color(red: 0.18, green: 0.55, blue: 0.34))
                .cornerRadius(8)
                
            }
            .navigationTitle("Plant Moisture Monitor")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Settings") {
                        showingSettings = true
                    }
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    HStack {
                        Circle()
                            .fill(networkManager.isConnected ? Color.green : Color.red)
                            .frame(width: 10, height: 10)
                        Text(networkManager.connectionStatus)
                            .font(.caption)
                    }
                }
            }
            .sheet(isPresented: $showingSettings) {
                SettingsView(networkManager: networkManager)
            }
        }
        .background(Color(red: 0.18, green: 0.55, blue: 0.34))
    }
}
// MARK: - Plant Tile View
struct PlantTileView: View {
    let plant: PlantData
    @ObservedObject var networkManager: NetworkManager
    @State private var showingDetails = false
    @State private var showingThresholds = false
    @State private var editingName = false
    @State private var plantName: String
    
    init(plant: PlantData, networkManager: NetworkManager) {
        self.plant = plant
        self.networkManager = networkManager
        self._plantName = State(initialValue: plant.config.name)
    }
    
    var moistureStatus: MoistureStatus {
        networkManager.getMoistureStatus(voltage: plant.voltage, plantId: plant.id)
    }
    
    var body: some View {
        VStack(spacing: 5) {
            // Name and alert
            HStack {
                if editingName {
                    TextField("Plant Name", text: $plantName)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .font(.system(size: 12))
                        .onSubmit {
                            networkManager.updatePlantName(plant.id, name: plantName)
                            editingName = false
                        }
                } else {
                    Text(plant.config.name)
                        .font(.system(size: 12, weight: .bold))
                        .onTapGesture {
                            editingName = true
                        }
                }
                
                Spacer()
                
                if moistureStatus.showAlert {
                    Text("!")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(.red)
                }
            }
            .padding(.horizontal, 8)
            
            // Plant image placeholder
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.gray.opacity(0.3))
                .frame(width: 40, height: 40)
                .overlay(
                    Text("🌱")
                        .font(.system(size: 20))
                )
            
            // Status
            Text(moistureStatus.statusText)
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(.black)
                .multilineTextAlignment(.center)
                .frame(height: 30)
            
            // Voltage
            Text("Voltage: \(String(format: "%.2f", plant.voltage)) V")
                .font(.system(size: 8))
                .foregroundColor(.black)
            
            // Progress bar
            ProgressView(value: moistureStatus.progressValue, total: 100)
                .scaleEffect(x: 1, y: 0.8)
                .padding(.horizontal, 8)
            
            // Buttons
            HStack(spacing: 4) {
                Button("Thresholds") {
                    showingThresholds = true
                }
                .buttonStyle(CompactButtonStyle(color: .green))
                
                Button("Details") {
                    showingDetails = true
                }
                .buttonStyle(CompactButtonStyle(color: .blue))
            }
            .padding(.horizontal, 8)
        }
        .padding(8)
        .background(moistureStatus.statusColor)
        .cornerRadius(10)
        .frame(width: 120, height: 180)
        .sheet(isPresented: $showingDetails) {
            PlantDetailsView(plant: plant, networkManager: networkManager)
        }
        .sheet(isPresented: $showingThresholds) {
            ThresholdsView(plant: plant, networkManager: networkManager)
        }
    }
}

// MARK: - Compact Button Style
struct CompactButtonStyle: ButtonStyle {
    let color: Color
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 6, weight: .bold))
            .foregroundColor(.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color)
            .cornerRadius(4)
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
    }
}

//// MARK: - Plant Details View
//struct PlantDetailsView: View {
//    let plant: PlantData
//    @ObservedObject var networkManager: NetworkManager
//    @Environment(\.dismiss) private var dismiss
//    
//    var moistureStatus: MoistureStatus {
//        networkManager.getMoistureStatus(voltage: plant.voltage, plantId: plant.id)
//    }
//    
//    var body: some View {
//        NavigationView {
//            VStack(spacing: 20) {
//                Text(plant.config.name)
//                    .font(.title)
//                    .fontWeight(.bold)
//                
//                // Large plant image placeholder
//                RoundedRectangle(cornerRadius: 12)
//                    .fill(Color.gray.opacity(0.3))
//                    .frame(width: 120, height: 120)
//                    .overlay(
//                        Text("🌱")
//                            .font(.system(size: 60))
//                    )
//                
//                VStack(alignment: .leading, spacing: 10) {
//                    Text("Status: \(moistureStatus.statusText)")
//                        .font(.system(size: 16))
//                    
//                    Text("Voltage: \(String(format: "%.2f", plant.voltage)) V")
//                        .font(.system(size: 16))
//                    
//                    Text("Dry Threshold: \(String(format: "%.2f", plant.config.dryThreshold)) V")
//                        .font(.system(size: 16))
//                    
//                    Text("Wet Threshold: \(String(format: "%.2f", plant.config.wetThreshold)) V")
//                        .font(.system(size: 16))
//                    
//                    Text("Last Update: \(plant.lastUpdate.formatted(.dateTime.hour().minute().second()))")
//                        .font(.system(size: 16))
//                        .foregroundColor(.gray)
//                }
//                .padding()
//                .background(Color.gray.opacity(0.1))
//                .cornerRadius(12)
//                
//                Spacer()
//            }
//            .padding()
//            .navigationTitle("Plant Details")
//            .navigationBarTitleDisplayMode(.inline)
//            .toolbar {
//                ToolbarItem(placement: .navigationBarTrailing) {
//                    Button("Done") {
//                        dismiss()
//                    }
//                }
//            }
//        }
//    }
//}
//
//// MARK: - Thresholds View
//struct ThresholdsView: View {
//    let plant: PlantData
//    @ObservedObject var networkManager: NetworkManager
//    @Environment(\.dismiss) private var dismiss
//    
//    @State private var dryThreshold: String
//    @State private var wetThreshold: String
//    @State private var showingError = false
//    @State private var errorMessage = ""
//    
//    init(plant: PlantData, networkManager: NetworkManager) {
//        self.plant = plant
//        self.networkManager = networkManager
//        self._dryThreshold = State(initialValue: String(format: "%.2f", plant.config.dryThreshold))
//        self._wetThreshold = State(initialValue: String(format: "%.2f", plant.config.wetThreshold))
//    }
//    
//    var body: some View {
//        NavigationView {
//            VStack(spacing: 20) {
//                Text("Set Thresholds for \(plant.config.name)")
//                    .font(.title2)
//                    .fontWeight(.bold)
//                    .multilineTextAlignment(.center)
//                
//                VStack(alignment: .leading, spacing: 15) {
//                    VStack(alignment: .leading) {
//                        Text("Dry Threshold (V):")
//                            .font(.system(size: 16))
//                        TextField("0.00", text: $dryThreshold)
//                            .textFieldStyle(RoundedBorderTextFieldStyle())
//                            .keyboardType(.decimalPad)
//                    }
//                    
//                    VStack(alignment: .leading) {
//                        Text("Wet Threshold (V):")
//                            .font(.system(size: 16))
//                        TextField("0.00", text: $wetThreshold)
//                            .textFieldStyle(RoundedBorderTextFieldStyle())
//                            .keyboardType(.decimalPad)
//                    }
//                }
//                .padding()
//                
//                Button("Save") {
//                    saveThresholds()
//                }
//                .buttonStyle(.borderedProminent)
//                .controlSize(.large)
//                
//                if showingError {
//                    Text(errorMessage)
//                        .foregroundColor(.red)
//                        .font(.caption)
//                }
//                
//                Spacer()
//            }
//            .padding()
//            .navigationTitle("Thresholds")
//            .navigationBarTitleDisplayMode(.inline)
//            .toolbar {
//                ToolbarItem(placement: .navigationBarTrailing) {
//                    Button("Cancel") {
//                        dismiss()
//                    }
//                }
//            }
//        }
//    }
//    
//    private func saveThresholds() {
//        guard let dry = Double(dryThreshold),
//              let wet = Double(wetThreshold) else {
//            showError("Enter valid numbers")
//            return
//        }
//        
//        guard dry >= 0.0 && dry <= 3.3 && wet >= 0.0 && wet <= 3.3 && dry < wet else {
//            showError("Invalid values (0.0-3.3, dry < wet)")
//            return
//        }
//        
//        networkManager.updatePlantThresholds(plant.id, dryThreshold: dry, wetThreshold: wet)
//        dismiss()
//    }
//    
//    private func showError(_ message: String) {
//        errorMessage = message
//        showingError = true
//        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
//            showingError = false
//        }
//    }
//}
//
//// MARK: - Settings View
//struct SettingsView: View {
//    @ObservedObject var networkManager: NetworkManager
//    @Environment(\.dismiss) private var dismiss
//    
//    var body: some View {
//        NavigationView {
//            VStack(spacing: 20) {
//                Text("Settings")
//                    .font(.title)
//                    .fontWeight(.bold)
//                
//                VStack(alignment: .leading, spacing: 15) {
//                    Text("Connection Status: \(networkManager.connectionStatus)")
//                        .font(.system(size: 16))
//                    
//                    Text("Total Plants: \(networkManager.plants.count)")
//                        .font(.system(size: 16))
//                    
//                    Text("Dry Plants: \(networkManager.dryPlants.count)")
//                        .font(.system(size: 16))
//                        .foregroundColor(.red)
//                }
//                .padding()
//                .background(Color.gray.opacity(0.1))
//                .cornerRadius(12)
//                
//                Spacer()
//            }
//            .padding()
//            .navigationTitle("Settings")
//            .navigationBarTitleDisplayMode(.inline)
//            .toolbar {
//                ToolbarItem(placement: .navigationBarTrailing) {
//                    Button("Done") {
//                        dismiss()
//                    }
//                }
//            }
//        }
//    }
//}
//
//// MARK: - App Entry Point
//@main
//struct PlantMonitorApp: App {
//    var body: some Scene {
//        WindowGroup {
//            ContentView()
//        }
//    }
//}
