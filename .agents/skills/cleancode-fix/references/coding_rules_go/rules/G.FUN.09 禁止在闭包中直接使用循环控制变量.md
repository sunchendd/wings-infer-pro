# G.FUN.09 禁止在闭包中直接使用循环控制变量

- **规则ID**：778539c5-2068-4c1f-8e43-78e59f29f67c
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

严重

**【描述】**

因为goroutine、defer等的特性，闭包实际执行时使用到的循环控制变量的值，往往并不是我们所期望的。

因此，禁止在闭包中直接使用循环控制变量，建议通过入参显式地引入。

**【正确示例】**

```
##### 场景1：在循环中启动goroutine，在goroutine中直接使用循环控制变量。
- 修复示例：如果要在闭包中使用循环控制变量，可通过入参把循环控制变量显示地引入。

    ```go
    func main() {
        runtime.GOMAXPROCS(runtime.NumCPU())

        var group sync.WaitGroup

        for i := 0; i < 5; i++ {
            group.Add(1)
            go func(j int) {
                defer group.Done()
                // 符合：对循环语句的goroutine需要进行显式地索引变量调用，这样才能得到类似"0 1 2 3 4"期望结果
                fmt.Printf("%-2d", j) // 闭包内部使用局部变量
            }(i) // 符合：把循环控制变量显式地传给goroutine
        }

        group.Wait()
    }
    ```


```
**【错误示例】**

```
##### 场景1：在循环中启动goroutine，在goroutine中直接使用循环控制变量。
- 错误示例：

    ```go
    func main() {
        runtime.GOMAXPROCS(runtime.NumCPU())
        var group sync.WaitGroup

        for i := 0; i < 5; i++ {
            group.Add(1)
            go func() {
                defer group.Done()
                // 不符合： 输出结果为"5 5 5 5 5"，由于多个goroutine同时使用变量i，goroutine调用的函数闭包对外部变量使用
                // 了引用的方式，而Go运行时调度goroutine的实际时间不确定，这个结果并不是我们所期望的
                fmt.Printf("%-2d", i)
            }()
        }

        group.Wait()
    }
    ```


```
**【修复建议】**

如果要在闭包中使用循环控制变量，可通过入参把循环控制变量显式地引入。
