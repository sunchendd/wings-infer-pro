# G.CON.03 禁止拷贝锁或同步的对象

- **规则ID**：ae91248c-49f5-4c0c-8a7b-7dea19aa5048
- **更新时间**：2026-04-07 04:20:03

---

**【问题级别】**

严重

**【描述】**

1、正确使用锁，确保程序不存在死锁

2、确保加锁的代码范围合理，禁止在循环语句中使用defer语句释放锁（如果同时在循环内加锁，而不使用defer语句释放的情形除外）；禁止多次释放锁

3、禁止拷贝包含各种类型的锁或同步的对象（一般在sync包里定义了锁或同步的类型结构），只可以通过它的指针或接口等引用类型来传递此类对象的引用。

**【正确示例】**

```
var m sync.Mutex
func foo() {
    s := "the test string"
    m.Lock()
    defer m.Unlock() // 符合，lock外提，在循环外进行释放
    // doing some thing need locked
    ...
    for i := 0; i < len(s); i++ {
    }
    ...
    // will unlock here
}

```
**【错误示例】**

```
package errorlock
import (
 "fmt"
 "sync"
)

// For语句里面只有lock没有unlock:
var m sync.Mutex

func bad_test1() {
 for i := 0; i < len(s); i++ {
  m.Lock()
 }
}
func bad_test2() {
 for i := 0; i < len(s); i++ {
  m.Lock()
  defer m.Unlock() // 前面有defer ，不算
 }
}

// will unlock here:
// 递归场景，递归调用没有用到unlock
var m2 sync.Mutex

func bad_test4() {
 m2.Lock()
 bad_test4() //会发生死锁现象
 m2.Unlock()
}
func bad_test5() {
 m2.Lock()
 defer m2.Unlock() // 前面有defer ，不算
 bad_test5()       //会发生死锁现象
}

```
**【修复建议】**

锁使用完需要及时释放，且不能多重释放
