# G.SIT.01 避免类型可能不为空的接口变量和nil直接进行比较

- **规则ID**：2f32cf23-445b-475b-808b-42d5310fbd1a
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

严重

**【描述】**

此规则要求：如果函数/方法返回值类型中包含了错误类型，必须是error接口类型。



在将具体类型的错误赋值给error，或作为error的返回值时。具体类型的错误值不能是nil，当具体错误类型值为nil 时，不可直接赋值给error接口（规则4.3）。通过上述约定，以确保可使用err == nil为True来表示和判断调用函数操作成功。使用error接口类型作为错误返回值类型，而不是具体的错误类型，以防止在处理错误和错误传递过程中，接口类型值包含了具体错误类型的nil值。

**【正确示例】**

```
func do() error {    if bad() {

       return ErrBad

  }

   return nil

} func wrapDo() error {       // error (*doError, &{...}) or (nil, nil)

   return do()

} func main() {    err := wrapDo()

   fmt.Println(err == nil) // true

}

```
**【错误示例】**

```
func do() *doError {        // nil of type *doError

   return nil

} func wrapDo() error {       // error (*doError, nil)

   return do()             // nil of type *doError

} func main() {

   err := wrapDo()         // error (*doError, nil)

   // fmt.Println(err == nil) // false

   if err == nil {

       fmt.Println("Success")

  } else {

       fmt.Println("Failed")

  }

}

```
**【修复建议】**

使用error作为函数的错误返回值类型
