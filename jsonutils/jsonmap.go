package jsonutils

/*
from https://github.com/go-testfixtures/testfixtures/blob/master/json.go

The MIT License (MIT)

Copyright (c) 2016 Andrey Nering

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

import (
	"database/sql/driver"
	"encoding/json"
)

var (
	_ driver.Valuer = JSONArray{}
	_ driver.Valuer = JSONMap{}
)

type JSONArray []interface{}

func (a JSONArray) Value() (driver.Value, error) {
	return json.Marshal(a)
}

type JSONMap map[string]interface{}

func (m JSONMap) Value() (driver.Value, error) {
	return json.Marshal(m)
}

// Go refuses to convert map[interface{}]interface{} to JSON because JSON only support string keys
// So it's necessary to recursively convert all map[interface]interface{} to map[string]interface{}
func RecursiveToJSON(v interface{}) (r interface{}) {
	switch v := v.(type) {
	case []interface{}:
		for i, e := range v {
			v[i] = RecursiveToJSON(e)
		}
		r = JSONArray(v)
	case map[interface{}]interface{}:
		newMap := make(map[string]interface{}, len(v))
		for k, e := range v {
			newMap[k.(string)] = RecursiveToJSON(e)
		}
		r = JSONMap(newMap)
	default:
		r = v
	}
	return
}
