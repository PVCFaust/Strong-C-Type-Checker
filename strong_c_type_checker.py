# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2024  Jakob Kalus

import collections.abc
import os
import subprocess
import sys
import typing

import clang.cindex



def print_list(list_to_print: collections.abc.Iterable[typing.Any]) -> None:
	for item in list_to_print:
		print(item)

def print_cursors_recursive(
		cursor_list: collections.abc.Iterable[clang.cindex.Cursor],
		depth: int
	) -> None:
	
	for cursor in cursor_list:
		print_cursor(cursor, depth)
		print_cursors_recursive(cursor.get_children(), depth + 1)

def print_cursors(
		cursor_list: collections.abc.Iterable[clang.cindex.Cursor],
		depth: int
	) -> None:
	
	for cursor in cursor_list:
		print_cursor(cursor, depth)

def print_cursor(cursor: clang.cindex.Cursor, depth: int) -> None:
	kind = "    " * depth + str(cursor.kind)
	print(f"{kind:<64} {cursor.displayname:<64} {cursor.type.spelling:<64}")
	#print(f"{kind:<64} {cursor.type.spelling:<64} {cursor.type.get_canonical().spelling:<64}")

def print_indent(string: str, depth: int) -> None:
	print("    " * depth + string)

def print_error(*args: typing.Any, **kwargs: typing.Any) -> None:
	print(*args, file=sys.stderr, **kwargs)





def handle_children(cursor: clang.cindex.Cursor, depth: int) -> None:
	for child in cursor.get_children():
		#print_cursor(child, depth)
		
		handler_map = {
			clang.cindex.CursorKind.TYPEDEF_DECL: None,
			clang.cindex.CursorKind.STRUCT_DECL: None,
			clang.cindex.CursorKind.ENUM_DECL: None,
			clang.cindex.CursorKind.INTEGER_LITERAL: None,
			clang.cindex.CursorKind.FLOATING_LITERAL: None,
			clang.cindex.CursorKind.IMAGINARY_LITERAL: None,
			clang.cindex.CursorKind.STRING_LITERAL: None,
			clang.cindex.CursorKind.CHARACTER_LITERAL: None,
			clang.cindex.CursorKind.CXX_BOOL_LITERAL_EXPR: None,
			clang.cindex.CursorKind.FUNCTION_DECL: handle_function_definition,
			clang.cindex.CursorKind.BINARY_OPERATOR: handle_binary_operator,
			clang.cindex.CursorKind.CALL_EXPR: handle_call_expression,
			clang.cindex.CursorKind.VAR_DECL: handle_variable_declaration,
			clang.cindex.CursorKind.RETURN_STMT: handle_return_statement,
		}
		
		handler = handler_map.get(child.kind, handle_children)
		
		if handler is not None:
			handler(child, depth + 1)





functions: list[clang.cindex.Cursor] = list()

def handle_function_definition(cursor: clang.cindex.Cursor, depth: int) -> None:
	global functions
	
	functions += [cursor]
	
	for child in cursor.get_children():
		#print_cursor(child, depth)
		
		if child.kind is not clang.cindex.CursorKind.COMPOUND_STMT:
			continue
		
		handle_children(child, depth + 1)

def handle_binary_operator(cursor: clang.cindex.Cursor, depth: int) -> None:
	children = cursor.get_children()
	
	left = next(children)
	right = next(children)
	
	left = dive_if_unexposed_expression(left)
	right = dive_if_unexposed_expression(right)
	
	compare_cursor_types(
		left,
		right,
		cursor.location,
		"Type missmatch in binary operation:"
	)
	
	handle_children(cursor, depth)

def handle_call_expression(cursor: clang.cindex.Cursor, depth: int) -> None:
	global functions
	
	def depth_first(cursor: clang.cindex.Cursor) -> clang.cindex.Cursor:
		try:
			return depth_first(next(cursor.get_children()))
		except StopIteration:
			return cursor
	
	function_name: clang.cindex.Cursor = depth_first(cursor)
	
	called_function: clang.cindex.Cursor | None = None
	registered_parameters: list[clang.cindex.Cursor] = []
	called_parameters: list[clang.cindex.Cursor] = []
	
	for function in functions:
		if function.displayname.startswith(f"{function_name.displayname}("):
			for child in function.get_children():
				if child.kind is clang.cindex.CursorKind.PARM_DECL:
					registered_parameters += [child]
			called_function = function
			break
	
	if called_function is not None:
		called_parameters = list(cursor.get_children())[1:]
		
		for registered_parameter, called_parameter in zip(registered_parameters, called_parameters):
			compare_cursor_types(
				cursor_0 = registered_parameter,
				cursor_1 = called_parameter,
				cursor_location = called_parameter.location,
				message = f"Type missmatch in function call of \"{function_name.displayname}\":",
				tail = f"\tfunction defined @{called_function.location}",
			)
	
	handle_children(cursor, depth)

def handle_variable_declaration(cursor: clang.cindex.Cursor, depth: int) -> None:
	children = list(cursor.get_children())
	
	if len(children) != 0:
		variable = cursor
		
		definition = children[-1]
		definition = dive_if_unexposed_expression(definition)
		
		compare_cursor_types(
			cursor_0 = variable,
			cursor_1 = definition,
			cursor_location = cursor.location,
			message = "Type missmatch in variable declaration:",
		)
	
	handle_children(cursor, depth)

def handle_return_statement(cursor: clang.cindex.Cursor, depth: int) -> None:
	try:
		desired_return_type = next(cursor.get_children())
		
		actual_return_type = next(desired_return_type.get_children())
		actual_return_type = dive_if_unexposed_expression(actual_return_type)
		
		compare_cursor_types(
			cursor_0 = desired_return_type,
			cursor_1 = actual_return_type,
			cursor_location = cursor.location,
			message = "Type missmatch in return statement:",
		)
	except StopIteration:
		pass
	
	handle_children(cursor, depth)



def dive_if_unexposed_expression(cursor: clang.cindex.Cursor) -> clang.cindex.Cursor:
	if cursor.kind is clang.cindex.CursorKind.UNEXPOSED_EXPR:
		try:
			return dive_if_unexposed_expression(next(cursor.get_children()))
		except StopIteration:
			return cursor
	
	return cursor

def compare_cursor_types(
		cursor_0: clang.cindex.Cursor,
		cursor_1: clang.cindex.Cursor,
		cursor_location: clang.cindex.SourceLocation,
		message: str,
		#debug: bool = False,
		tail: str | None = None,
	) -> None:
	
	type_0 = cursor_0.type.spelling
	type_1 = cursor_1.type.spelling
	
	type_0_canonical = cursor_0.type.get_canonical().spelling
	type_1_canonical = cursor_1.type.get_canonical().spelling
	
	#if debug:
	#	print(str(type_0))
	#	print(str(type_1))
	
	if type_0 != type_1:
		if os.path.abspath(cursor_location.file.name) in available_includes:
			print_error(message)
			print_error(f"\t@{cursor_location}")
			
			print_error(f"\t\"{type_0}\" (\"{type_0_canonical}\") != \"{type_1}\" (\"{type_1_canonical}\")")
			
			if tail is not None:
				print_error(tail)
			
			print_error()





def get_available_includes(include_base_dirs: set[str]) -> set[str]:
	available = set()
	
	for base_dir in include_base_dirs:
		available_one = get_available_includes_one(base_dir)
		available |= available_one
	
	return available

def clean_walk(walk: collections.abc.Iterable[tuple[str, list[str], list[str]]]) -> set[str]:
	returner = set()
	
	for t in walk:
		files = {os.path.join(t[0], file) for file in t[2]}
		returner |= files
	
	return returner

def get_available_includes_one(include_base_dir: str) -> set[str]:
	walk = os.walk(include_base_dir)
	
	available = clean_walk(walk)
	available = {os.path.abspath(file) for file in available}
	
	return available





class ParsedArgs():
	def __init__(
			self,
			include_dirs: set[str],
			clang_args: list[str],
		):
		
		self.include_dirs = include_dirs
		self.clang_args = clang_args

def get_clang_includes() -> list[str]:
	returner = []
	
	clang_process = subprocess.run(
		args = ["clang", "-v", "-c", "-xc", "/dev/null"],
		capture_output = True
	)
	
	clang_output = clang_process.stderr.decode().split("\n")
	
	capture_includes = False
	
	for line in clang_output:
		if line == "End of search list.":
			capture_includes = False
		
		if capture_includes == True:
			returner += [line.strip()]
		
		if line == "#include <...> search starts here:":
			capture_includes = True
	
	return returner

def parse_args(argv: list[str]) -> ParsedArgs:
	
	include_dirs = set()
	clang_args = list()
	
	grab_next_as_include_dir = False
	
	for arg in argv:
		if arg.endswith(".c"):
			include_dirs |= {os.path.dirname(arg)}
		
		if arg == "-I":
			grab_next_as_include_dir = True
		
		if arg.startswith("-I"):
			include_dir = arg[2:]
			
			if include_dir != "":
				include_dirs |= {include_dir}
		
		if grab_next_as_include_dir:
			include_dirs |= {arg}
			grab_next_as_include_dir = False
		
		clang_args += [arg]
	
	
	
	default_includes = list()
	
	for include in get_clang_includes():
		default_includes += ["-I", include]
	
	clang_args = default_includes + clang_args
	
	
	
	return ParsedArgs(
		include_dirs = include_dirs,
		clang_args = clang_args,
	)





if __name__ == "__main__":
	
	index = clang.cindex.Index.create()
	
	parsed_args = parse_args(sys.argv[1:])
	
	#print_list(parsed_args.clang_args)
	
	available_includes = get_available_includes(parsed_args.include_dirs)
	
	#print_list(available_includes)
	
	translation_unit = index.parse(
		path = None,
		args = parsed_args.clang_args,
	)
	
	#for diag in translation_unit.diagnostics:
	#	print(diag.format)
	
	
	if os.path.isfile("./null.o"):
		os.remove("./null.o")
	
	#print_cursors_recursive(translation_unit.cursor.get_children(), 0)
	
	handle_children(translation_unit.cursor, 0)
