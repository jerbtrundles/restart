# Main.gd
extends Node2D

# --- Configuration ---
const H_SPACING = 300.0
const V_SPACING = 150.0

# --- Preload the Room Scene template ---
var RoomScene = preload("res://RoomScene.tscn")

# --- On-screen variables ---
var region_data: Dictionary = {}
var room_nodes: Dictionary = {}

# --- Camera Control variables ---
var camera_zoom = Vector2(0.5, 0.5)
var is_panning = false


# This function runs once when the scene is ready.
func _ready():
	# Path to your JSON file. "res://" is the root of your Godot project.
	var region_file_path = "res://data/regions/town.json"
	load_region_data(region_file_path)
	draw_map()


# This function handles all user input.
func _input(event):
	# Handle Mouse Wheel Zooming
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera_zoom *= 1.1
		if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera_zoom /= 1.1

	# Handle Panning Start
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.is_pressed():
		is_panning = true

	# Handle Panning End
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.is_pressed():
		is_panning = false

	# Handle Panning Motion
	if event is InputEventMouseMotion and is_panning:
		# We move the Node2D itself to simulate a camera
		self.position += event.relative * 0.8
		

# Main function to load the JSON file.
func load_region_data(file_path):
	var file = FileAccess.open(file_path, FileAccess.READ)
	if file == null:
		print("Error: Could not open file: ", file_path)
		return

	var content = file.get_as_text()
	var json = JSON.new()
	var error = json.parse(content)
	if error != OK:
		print("Error parsing JSON: ", json.get_error_message(), " at line ", json.get_error_line())
		return

	region_data = json.get_data()


# Main function to draw the map.
func draw_map():
	if not region_data.has("rooms"):
		print("Error: No 'rooms' key in region data.")
		return

	var rooms = region_data["rooms"]
	var room_positions = {} # To store calculated (x, y) for each room
	var queue = []
	
	# Find the first room to start the layout
	if rooms.keys().size() > 0:
		var start_id = rooms.keys()[0]
		queue.append(start_id)
		room_positions[start_id] = Vector2(0, 0)
	
	# Breadth-First Search to calculate layout and avoid overlap
	while not queue.is_empty():
		var current_id = queue.pop_front()
		var current_pos = room_positions[current_id]
		
		# Instance and configure the room node
		var room_node = RoomScene.instantiate()
		room_node.position = current_pos
		
		# Set the text on the labels
		room_node.get_node("Panel").get_node("Label").text = rooms[current_id].get("name", "Unknown")
		room_node.get_node("Panel").get_node("Label2").text = current_id
		
		add_child(room_node)
		room_nodes[current_id] = room_node
		
		# Explore exits
		if rooms[current_id].has("exits"):
			var i = 0
			for exit_dir in rooms[current_id]["exits"]:
				var dest_full_id = rooms[current_id]["exits"][exit_dir]
				var dest_parts = dest_full_id.split(":")
				var dest_id = dest_parts[-1]
				
				if rooms.has(dest_id) and not room_positions.has(dest_id):
					# Simple layout logic: place neighbors in a circle
					var angle = (float(i) / rooms[current_id]["exits"].size()) * 2 * PI
					var new_pos = current_pos + Vector2(cos(angle), sin(angle)) * H_SPACING
					
					room_positions[dest_id] = new_pos
					queue.append(dest_id)
					i += 1

	# Second pass to draw connection lines
	update_canvas()


# This function runs every frame.
func _process(delta):
	# Apply camera zoom
	self.scale = camera_zoom
	
	# Redraw the connection lines every frame
	update_canvas()


# Helper function to draw lines between rooms.
func update_canvas():
	# This tells the Node2D to call the _draw function
	queue_redraw()

# This is a special Godot function that is called when queue_redraw() is used.
func _draw():
	if not region_data.has("rooms"): return
	
	for room_id in region_data["rooms"]:
		if room_nodes.has(room_id) and region_data["rooms"][room_id].has("exits"):
			var start_pos = room_nodes[room_id].position
			for exit_dir in region_data["rooms"][room_id]["exits"]:
				var dest_full_id = region_data["rooms"][room_id]["exits"][exit_dir]
				var dest_parts = dest_full_id.split(":")
				var dest_id = dest_parts[-1]
				
				if room_nodes.has(dest_id):
					var end_pos = room_nodes[dest_id].position
					draw_line(start_pos, end_pos, Color.WHITE, 1.0)
