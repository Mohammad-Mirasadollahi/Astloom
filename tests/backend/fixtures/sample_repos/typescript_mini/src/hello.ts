export function greet(name: string): string {
  return `hello ${name}`;
}

export function main(): void {
  // eslint-disable-next-line no-console
  console.log(greet("astloom"));
}
