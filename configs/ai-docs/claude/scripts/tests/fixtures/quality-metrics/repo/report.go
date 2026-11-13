package main

func build_report(a int) int {
	if a > 1 {
		if a > 2 {
			if a > 3 {
				if a > 4 {
					return 1
				}
			}
		}
	}
	return 0
}

func trim_cell(a int, b int, c int) int {
	return a + b + c
}
