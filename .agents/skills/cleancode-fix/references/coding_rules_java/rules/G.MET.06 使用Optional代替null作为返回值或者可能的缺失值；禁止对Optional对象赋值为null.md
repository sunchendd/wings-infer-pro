# G.MET.06 使用Optional代替null作为返回值或者可能的缺失值；禁止对Optional对象赋值为null

- **规则ID**：9a325539-f5b3-4a4b-9ed3-7d0c86871aa5
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

使用`Optional`代替`null`作为返回值或者可能的缺失值；禁止对`Optional`对象赋值为`null`

工具检查场景:

- 检查是否将`null`赋值给`Optional`对象

- 检查是否将`Optional`对象和`null`进行比较（==或!=）

- 检查方法返回类型是否为`Optional<Integer>`、`Optional<Long>`或`Optional<Double>`

- 检查方法返回类型是否为`Optional<集合或数组>`

**【正确示例】**

```
##### 场景1：对于返回集合类型，应返回空集合

- 修复示例：返回空的集合

  ```java
    public List<String> doSomething() {
        ...
        return Collections.emptyList();
    }
  ```

##### 场景2：对于包装类型应该使用OptionalInt、OptionalLong、OptionalDouble

- 修复示例：使用OptionalInt

  ```java
    public OptionalInt doSomething() {
        ...
        return OptionalInt.of(1);
    }
  ```

##### 场景3：禁止对Optional对象赋值/返回为null

- 修复示例：返回Optional.empty()
  ```java
    public OptionalInt doSomething() {
        ...
        return Optional.empty();
    }
  ```

##### 场景4：禁止Optional与null进行比较


- 修复示例：使用Optional.empty()来做判空逻辑
  ```java
    public void doSomething(Optional<String> opt) {
        ...
        if(opt.isEmpty()) {
        ...
        }
    }
  ```

```
**【错误示例】**

```
##### 场景1：对于返回集合类型，应返回空集合

- 错误示例：使用了Optional<集合或数组>

  ```java
    public Optional<List<String>> doSomething() {
        ...
        return Optional.empty();
    }
  ```

##### 场景2：对于包装类型应该使用OptionalInt、OptionalLong、OptionalDouble

- 错误示例：使用了Optional<Integer>

  ```java
    public Optional<Integer> doSomething() {
        ...
        return Optional.of(1);
    }
  ```

##### 场景3：禁止对Optional对象赋值/返回为null

- 错误示例：返回值为Optional<>的方法返回了null

  ```java
    public Optional<String> doSomething() {
        ...
        return null;
    }
  ```

##### 场景4：禁止Optional与null进行比较

- 错误示例：将`Optional`对象和`null`进行比较（==或!=）

  ```java
    public void doSomething(Optional<String> opt) {
        ...
        if(opt==null) {
        ...
        }
    }
  ```

```
**【修复建议】**

**禁止对Optional对象赋值/返回为null，或与null比较**，例如: `Optional<Foo> foo = null;`；

不应该返回`Optional<Integer>`、`Optional<Long>`、`Optional<Double>`，而应该使用`OptionalInt`、`OptionalLong`、`OptionalDouble` ；

一般不应该返回`Optional<集合或数组>`，而用空集合或空数组替代。
