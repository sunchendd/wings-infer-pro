# G.MEM.02 禁止解引用空的接口和内置引用类型变量

- **规则ID**：ae42249f-1508-4bbc-8d98-926ce8b553c5
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

解引用空的接口和内置引用类型变量可能会引发panic。

**【正确示例】**

```
##### 场景1：解引用空接口
- 修复示例：接口使用前判空

    ```go
    type Mystruct struct {

    }

    func (this *Mystruct) foo() {

    }

    type MyInterface interface {
         foo()
    }

    func main() {
        var i MyInterface
        if i != nil {    // 符合：合法性校验
            i.foo()
        }
    }
    ```
##### 场景2：解引用slice
- 修复示例：

    ```go
    func main() {
        var x []int8 = make([]int8, 6) // 符合：初始化
        x[3] = 10
        fmt.Println(x)
    }
    ```
##### 场景3：解引用chan
- 修复示例：
    ```go
    func main() {
        var ch chan int = make(chan int, 6) // 符合：初始化
        go func() {
            for i := 3; i >= 0; i-- {
                ch <- i
                time.Sleep(time.Second)
            }
        }()
        for data := range ch {
            fmt.Println(data)
            if data == 0 {
                break
            }
        }
    }
    ```
##### 场景4：解引用map
- 修复示例：
    ```go
    func main() {
        var my_map map[string]string = make(map[string]string) // 符合：初始化
        my_map["name"] = "Alice"
        fmt.Println(my_map["name"])
    }
    ```


```
**【错误示例】**

```
##### 场景1：解引用空接口
- 错误示例：
    ```go
    type Mystruct struct {

    }

    func (this *Mystruct) foo() {

    }

    type MyInterface interface {
        foo()
    }

    func main() {
        var i MyInterface
        // 不符合：解引用空接口
        i.foo()
    }
    ```
##### 场景2：解引用slice
- 错误示例：
    ```go
    func main() int {
        ...
        var x []int8
        // 不符合：slice 未初始化被调用
        x[3] = 10
        fmt.Println(x)
    }
    ```
##### 场景3：解引用chan
- 错误示例：
    ```go
    func main() {
        var ch chan int
        // 不符合：chan 未初始化被调用
        go func() {
            for i := 3; i >= 0; i-- {
                ch <- i
                time.Sleep(time.Second)
            }
        }()
        for data := range ch {
            fmt.Println(data)
            if data == 0 {
                break
            }
        }
    }
    ```
##### 场景4：解引用map
- 错误示例：
    ```go
    func main() {
        var my_map map[string]string
        // 不符合：my_map 未初始化被调用
        my_map["name"] = "Alice"
        fmt.Println(my_map["name"])
    }
    ```


```
**【修复建议】**

禁止解引用空的接口和内置引用类型变量。

1. 对slice、chan、map内置引用类型的变量，在访问变量的元素值前，必须使用make显式初始化（对值为nil的slice进行append操作除外，此操作将产生一个新的slice）。

2. 对interface类型变量，在解引用或调用变量方法之前，应判断接口变量不为空。
