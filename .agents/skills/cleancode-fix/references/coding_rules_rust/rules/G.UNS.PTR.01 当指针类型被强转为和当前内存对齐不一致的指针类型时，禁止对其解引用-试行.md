# G.UNS.PTR.01 当指针类型被强转为和当前内存对齐不一致的指针类型时，禁止对其解引用-试行

- **规则ID**：d7599c25-efb0-4cbb-8a97-837622c0c5e0
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

提示

**【描述】**

该 Lint 会检查是否出现 指针类型被强转为和当前内存对齐不一致的指针类型 的情况，要注意不要对这类强转后的指针进行解引用操作，否则会有未定义行为。

**【正确示例】**

```
fn main() {
    let a = (&1u8 as *const u8) as *const u8;
    let b = (&mut 1u8 as *mut u8) as *mut u8;
    let c =  (&1u8 as *const u8).cast::<u8>();
   
    // safe
    unsafe { *a }; 
    // safe
    unsafe { *b }; 
    // safe
    unsafe { *c }; 
}

```
**【错误示例】**

```
fn main() {
    let a = (&1u8 as *const u8) as *const u16;
    let b = (&mut 1u8 as *mut u8) as *mut u16;
    let c =  (&1u8 as *const u8).cast::<u16>();
    // Undefined Behavior: dereferencing pointer failed: alloc1411 has size 1, so pointer to 2 bytes starting at offset 0 is out-of-bounds
    unsafe { *a }; 
    // Undefined Behavior: dereferencing pointer failed: alloc1411 has size 1, so pointer to 2 bytes starting at offset 0 is out-of-bounds
    unsafe { *b }; 
    // Undefined Behavior: dereferencing pointer failed: alloc1411 has size 1, so pointer to 2 bytes starting at offset 0 is out-of-bounds
    unsafe { *c }; 
}

```
**【修复建议】**
