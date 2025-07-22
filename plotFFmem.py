import gzip
import json
import argparse
import sys
import plotly.express as px

def load_flat_reports(filename):
	# Open the gzipped file in binary read mode
	with gzip.open(filename, 'rb') as f:
		# Read the content as bytes
		gzipped_content = f.read()
		# Decode the bytes to a string, using 'utf-8' and 'ignore' errors
		# 'ignore' will skip characters that cannot be decoded,
		# which might be acceptable for some corrupted parts or non-standard characters.
		# If strict adherence to valid UTF-8 is required, 'replace' or 'backslashreplace'
		# could also be considered, or raising an error for invalid characters.
		decoded_content = gzipped_content.decode('utf-8', errors='ignore')
		# Load the JSON from the decoded string
		return json.loads(decoded_content)

def bytes_to_mb(num_bytes):
	return num_bytes / 1048576

def insert_path(tree, path_parts, amount):
	node = tree
	for part in path_parts:
		if part not in node['children']:
			node['children'][part] = {'name': part, 'amount': 0, 'children': {}}
		node = node['children'][part]
	node['amount'] += amount

def sum_amounts(node):
	if node['children']:
		# Ensure that 'amount' is explicitly summed from children
		node['amount'] = sum(sum_amounts(child) for child in node['children'].values())
	return node['amount']


def build_explicit_tree_for_all_processes(reports):
	processes = sorted(set(r["process"] for r in reports if r["path"] == "explicit" or r["path"].startswith("explicit/")))
	tree = {'name': 'All Processes', 'amount': 0, 'children': {}}
	for proc in processes:
		proc_tree = {'name': proc, 'amount': 0, 'children': {}}
		for r in reports:
			if r["process"] != proc:
				continue
			if not (r["path"] == "explicit" or r["path"].startswith("explicit/")):
				continue
			path_parts = r["path"].split("/")
			insert_path(proc_tree, path_parts, r.get("amount", 0))
		sum_amounts(proc_tree)
		tree['children'][proc] = proc_tree
	sum_amounts(tree)
	return tree

def get_top_nodes_by_fraction(tree, fraction=0.5):
	# tree['children'] are level-1 nodes (processes)
	children = list(tree['children'].values())
	children.sort(key=lambda n: n['amount'], reverse=True)
	total = sum(child['amount'] for child in children)
	running = 0
	top_names = set()
	for child in children:
		running += child['amount']
		top_names.add(child['name'])
		if running >= total * fraction:
			break
	return top_names

def flatten_tree_adaptive(node, parent_path, labels, parents, values, hover_texts,
							process_deep, base_depth, max_depth, current_depth=0, process_name=None):
	label = node['name']
	this_path = parent_path + "/" + label if parent_path else label

	# Determine process for this node
	# The 'All Processes' node is at depth 0, its children (the actual processes) are at depth 1.
	# So, if parent_path is "All Processes", the current 'label' is a process name.
	if current_depth == 1 and parent_path == "All Processes":
		process_name = label
	elif current_depth == 0: # For the "All Processes" root node itself
		process_name = None # No specific process name yet

	# Add node to sunburst
	if parent_path:  # skip synthetic root ('All Processes' node itself)
		labels.append(this_path)
		parents.append(parent_path)
		values.append(bytes_to_mb(node['amount']))
		hover_texts.append(f"{this_path}<br>{bytes_to_mb(node['amount']):,.2f} MB")

	# Determine depth limit for this process
	# If process_name is None, it means we are at the "All Processes" root or an intermediate
	# node before a process is identified. In such cases, we should use max_depth to ensure
	# that the process nodes themselves are always explored, and then the depth limit
	# will apply to their children.
	if process_name and process_name in process_deep:
		depth_limit = max_depth
	else:
		depth_limit = base_depth

	# Only recurse if current depth is less than the determined depth limit
	# The current_depth here refers to the depth *of the children* if we were to recurse.
	# So, if current_depth is already at depth_limit, we should not recurse further.
	if current_depth < depth_limit:
		for child in node['children'].values():
			flatten_tree_adaptive(child, this_path, labels, parents, values, hover_texts,
								  process_deep, base_depth, max_depth, current_depth + 1, process_name)


def main():
	parser = argparse.ArgumentParser(
		description="Globally adaptive-depth sunburst for 'explicit' allocations in Firefox about:memory JSON.gz."
	)
	parser.add_argument("filename", help="Path to the about:memory JSON.gz file")
	parser.add_argument("--base-depth", type=int, default=3, help="Depth for small processes (default: 3)")
	parser.add_argument("--max-depth", type=int, default=6, help="Depth for large processes (default: 6)")
	parser.add_argument("--fraction", type=float, default=0.5, help="Fraction of total to unroll deeply (default: 0.5)")
	args = parser.parse_args()

	try:
		data = load_flat_reports(args.filename)
		reports = data["reports"]

		tree = build_explicit_tree_for_all_processes(reports)
		top_processes = get_top_nodes_by_fraction(tree, args.fraction)

		labels, parents, values, hover_texts = [], [], [], []
		flatten_tree_adaptive(
			tree, "", labels, parents, values, hover_texts,
			process_deep=top_processes,
			base_depth=args.base_depth,
			max_depth=args.max_depth
		)

		fig = px.sunburst(
			names=labels,
			parents=parents,
			values=values,
			title=f"about:memory (All Processes, Explicit Allocations, Adaptive Depth)",
			custom_data=[hover_texts, values]
		)
		fig.update_traces(
			hovertemplate='<b>%{customdata[0]}</b><br>RAM Usage: %{customdata[1]:,.2f} MB<extra></extra>',
			insidetextorientation='radial'
		)
		fig.show()
	except Exception as e:
		print(f"Error: {e}", file=sys.stderr)
		sys.exit(1)

if __name__ == "__main__":
	main()