# G.CON.07 创建新线程时必须指定线程名

- **规则ID**：ecefaa6d-19bc-45f5-bba8-751774817240
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

指定线程名可以给问题定位带来很多方便。日志或者dump文件中会包含线程的名字，但缺省的线程名Thread-n无法区分出是哪个线程，不便于问题定位。

**【正确示例】**

```
##### 场景1：
- 修复示例： 


  ```java
    Thread t1 = new Thread();
    t1.setName("xxx");
    t1.start();
    
    Thread t2 = new Thread();
    t2.setName("xxx");
    t2.start();
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

  ```java
    Thread t1 = new Thread();
    t1.start(); // 没有指定线程名
    
    Thread t2 = new Thread();
    t2.start();
    t2.setName("xxx"); // 线程启动后再指定线程名无效
  ```


```
**【修复建议】**

创建线程时为线程指定具体的名称。
