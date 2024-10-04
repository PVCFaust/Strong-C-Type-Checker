# Strong C Type Checker

## Introduction:
The keyword `typedef` in C does not, contrary to its name, define a new type.
It merely defines a _type alias_.
This means that even though a `typedef int amount` and a `typedef int length` are conceptually different,
variables defined as these different types are compatible with each other.
Assigning a `length` to an `amount` is perfectly legal, because the underlying type for both is `int`.

## What is this?
This is a simple static analysis script for C to find any statements which do not exactly match the defined type.
This includes `typedef`s as distict types.

## Requirements:
- The python module `libclang` and all of its requirements

## Usage:
```bash
python strong_c_type_checker.py <the same arguments you would use to compile something with clang>
```
Any found type missmatch is reported to stderr.

## Limitations:
- This checker is _extremely_ strict. Unless the type matches _exactly_, a type missmatch is reported.
- Types for operations are sometimes weird and give rise to false positives.
- If you use tabs in your code, the reported location in the source may not be accurate.
  libclang counts the tab character `\t` as one column when displaying a `SourceLocation`.
- For some reason libclang always creates the file `null.o` in the current working directory.

## License:
Strong C Type Checker

Copyright (C) 2024  Jakob Kalus

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
