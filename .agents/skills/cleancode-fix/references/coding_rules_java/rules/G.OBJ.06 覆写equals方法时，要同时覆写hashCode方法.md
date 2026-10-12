# G.OBJ.06 覆写equals方法时，要同时覆写hashCode方法

- **规则ID**：5b3d1eaf-3b14-4442-8203-d4adc4352c70
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

严重

**【描述】**

当对象需要进行逻辑相等的比较时（比如判断String、Integer对象中的值是否相同），应对Object的equals()方法进行覆写，实现具体的判断逻辑。覆写equals()方法时，要同步覆写hashCode()方法。Java对象在存放到基于Hash的集合（如HashMap、HashTable等）时，会使用其Hash码进行索引，如果只覆写了equals()方法，而没有正确覆写hashCode()方法，则会导致效率低下甚至出错。Java对象的hashCode()方法有如下约定：



- 同一次运行中，同一个对象如果equals方法中用到的信息没有改变，多次调用其hashCode方法返回值必须相同；

- 如果对两个对象调用equals方法时相等，则这两个对象的hashCode方法，也必须返回相同的值；

- 如果对两个对象调用equals方法时不相等，则对这两个对象的hashCode方法，不要求其返回值不同，但是出于减少哈希碰撞的性能考虑，最好能不同。

**【正确示例】**

```
##### 场景1：
- 修复示例：同步覆写`equals()`方法和`hashcode()`方法

```java
public class Entity {
    private String id;
    private String value;
    @Override
    public boolean equals(Object obj) {
        ...
        if (obj instanceof Entity) {
            Entity that = (Entity) obj;
            return Objects.equals(this.id, that.id)
                && Objects.equals(this.value, that.value);
        }
        ...
        return false;
    }

    // 【GOOD】覆写`equals()`方法时，需要同步覆写`hashCode()`方法
	@Override
    public int hashCode() {
        int result = 0;
        ...
        return result;        
    }
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：仅覆写`equals()`方法，未同步覆写`hashcode()`方法

```java
public class Entity {
    private String id;
    private String value;
    @Override
    public boolean equals(Object obj) {
        ...
        if (obj instanceof Entity) {
            Entity that = (Entity) obj;
            return Objects.equals(this.id, that.id)
                && Objects.equals(this.value, that.value);
        }
        ...
        // 【不符合】未覆写`hashCode()`方法
        return false;
    }
}
```


```
**【修复建议】**

覆写`equals()`方法时，需要同步覆写`hashCode()`方法。
