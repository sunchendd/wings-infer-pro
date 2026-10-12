# G.ASY.02 在跨await 调用中持有同步锁需要进行处理-试行

- **规则ID**：888bafb1-8799-4732-a45f-739a032b1151
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

同步互斥锁本来就不是为异步上下文跨 await 调用而设计的，在这种场景中使用同步互斥锁容易造成死锁。当同步互斥锁被跨 await 时，有可能很长时间都不会返回这个调用点，在其他任务中再次用到这个互斥锁的时候，容易造成死锁。



这里有三种解决方案：



使用异步互斥锁。但是异步互斥锁的开销要大于同步互斥锁。

确保同步互斥锁在调用 await 之前已经释放。

**【正确示例】**

```
use std::sync::Mutex;
// 使用同步互斥锁
async fn foo(x: &Mutex<u32>) {
    {
        let guard = x.lock().unwrap();
        *guard += 1;
    }
    bar.await;
}
// 使用异步互斥锁
use tokio::sync::Mutex;
use std::sync::Arc;
#[tokio::main]
async fn main() {
    // 使用 Arc 允许跨线程共享 Mutex
    let count = Arc::new(Mutex::new(0));
    for i in 0..5 {
        let my_count = Arc::clone(&count);
        tokio::spawn(async move {
            for j in 0..10 {
                // 这里的 lock 在每次迭代后都会被释放
                let mut lock = my_count.lock().await;
                *lock += 1;
                println!("{} {} {}", i, j, lock);
            }
        });
    }
    loop {
        // 这里的 lock 在每次迭代后都会被释放
        if *count.lock().await >= 50 {
            break;
        }
    }
    println!("Count hit 50.");
}

```
**【错误示例】**

```
use std::sync::Mutex;
async fn foo(x: &Mutex<u32>) {
  let guard = x.lock().unwrap();
  *guard += 1;
  bar.await;
}

```
**【修复建议】**
