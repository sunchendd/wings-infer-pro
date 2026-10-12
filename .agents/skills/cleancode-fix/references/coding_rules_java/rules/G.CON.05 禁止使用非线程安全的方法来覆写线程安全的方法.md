# G.CON.05 禁止使用非线程安全的方法来覆写线程安全的方法

- **规则ID**：0b8c7abf-7fc9-4d6b-bc59-cd16b30d43ce
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

对于线程安全的方法被子类覆写为非线程安全时，可能会因为数据竞争（不正确的同步）导致难以定位的问题产生。

**【正确示例】**

```
##### 场景1：同步方法。
- 修复示例：

```java
class SeniorClass {
    public synchronized void doSomething() {
        ...
    }
}

class JuniorClass extends SeniorClass {
    @Override
    public synchronized void doSomething() { // 保持与父类一致。
        ...
    }
}
```


```
**【错误示例】**

```
##### 场景1：同步方法。
- 错误示例：

```java
class SeniorClass {
    public synchronized void doSomething() {
        ...
    }
}

class JuniorClass extends SeniorClass {
    @Override
    public void doSomething() { // doSomething()在被子类覆写时，改为了非线程安全的方法。
        ...
    }
}
```


```
**【修复建议】**

子类覆写父类方法，父类方法需要进行线程同步保护时，子类中的方法也要保持同步。
